# Claude independence: edakit with Copilot, Qwen, Mistral and OpenCode, and with self-hosted models

Status 2026-11-01: decided. Asked for by the owner ("write a concept – Claude independence; I want to open it for Qwen
and Llama, Mistral and Copilot"), where "Llama" meant running models oneself – "I mean the LLM self-hosting, not the LLM
itself" –; decisions 1, 2 and 4 taken by the owner the same day in a decision round in Claude Code's form, the rest
decided by Claude on the owner's word ("make a proposal") and confirmed by the owner the same day (the table at the
end); OpenCode added by the owner the same day ("maybe OpenCode integration too?"); nothing built – the steps CI.0 to
CI.7 start on the owner's word, listed in `TODO.md`. Written against main at `e4b82a0`. The findings on edakit come from
its code, skills, agents, hooks, tests and evals at that commit; those on the other harnesses and models from their
documentation and source, read on 2026-11-01 from the repositories the sites are built from – docs.github.com and
code.visualstudio.com were not reachable from the session, their sources were –, each with its commit or date under
"Sources". What rests only on search summaries is marked so.

## The short answer

edakit's checks are independent of Claude already: the command line, the catalog, the engines, the simulation, the gate
and the EasyEDA MCP server run without Claude Code (`uvx … edakit <command>`). What binds edakit to Claude is the layer
that steers the model: the plugin's format and marketplace, two hooks in Claude Code's protocol, the session identity
behind the EasyEDA claim, 27 paths through `${CLAUDE_PLUGIN_ROOT}`, two tool names – AskUserQuestion and Claude in
Chrome –, MCP tool names in three agents, and the eval runner.

The ground has moved in edakit's favour. Claude Code's plugin format has become the format others read: GitHub Copilot's
CLI installs plugins with `.claude-plugin/plugin.json` and `marketplace.json`, gives Claude-format hooks Claude's
payloads and matchers, and hands plugin hooks `CLAUDE_PLUGIN_ROOT`; since VS Code 1.143 its default agent runs the same
runtime. Qwen Code installs Claude Code plugins and converts their agents, skills, hooks and MCP servers. Mistral Vibe
imports a plugin's skills and MCP servers, not yet its agents and hooks. Agent Skills (`SKILL.md`) and `AGENTS.md` are
read by all of them.

Proposed: **the plugin made portable once**, so that Copilot, Qwen Code and – for skills and MCP – Vibe take it from the
same marketplace; **project files generated from the plugin** for what a harness does not take (Vibe's agents, the
working agreements where a harness has no session-start hook, and OpenCode, which takes no plugin but reads skills,
Markdown sub-agents and TypeScript plugins); a few things moved into the command line, where every harness reaches them;
and **support measured, not claimed** – the evals run for every pair of harness and model, and the README names the
pairs that pass.

Two findings set the expectations. **Self-hosting** works in all four harnesses – Copilot through the user's own key
with Ollama or any OpenAI-compatible endpoint, Qwen Code through an OpenAI-compatible base URL, Vibe through its
llama.cpp provider, OpenCode through Ollama, llama.cpp, vLLM or LM Studio –, so that a project's files can stay on the
user's machine. And the open models are behind on long agentic work – in Qwen's own report its newest coding model
scores 25.8 on Terminal-Bench 2.0 in Qwen Code against 37.1 for Claude Sonnet 4.5; edakit's checks catch a wrong result,
not a model that stops halfway. edakit's own development – the sessions in this repository, CLAUDE.md, the Action
proposals – stays on Claude.

## What binds edakit to Claude today

| Place | What is Claude Code's | Where it binds |
| --- | --- | --- |
| `.claude-plugin/plugin.json`, `marketplace.json` | the plugin format; the EasyEDA server started with `${CLAUDE_PLUGIN_ROOT}` in its arguments | distribution, the MCP server's start |
| `skills/*/SKILL.md` (13) | front matter `name`, `description` – Agent Skills – and `argument-hint`; `${CLAUDE_PLUGIN_ROOT}` 27 times in 18 skills and agents, 18 of them paths into the handbook; AskUserQuestion in decision-round and new-project; Claude in Chrome in cart and release | paths, two tools |
| `agents/*.md` (7) | front matter `name`, `description`, `tools`; 3 tool lists name `mcp__plugin_edakit_easyeda__…` | the plugin's MCP tool names |
| `hooks/hooks.json` | SessionStart: `edakit/agreements.py` answers with `hookSpecificOutput.additionalContext`; PreToolUse: `edakit/lock.py` with `permissionDecision: deny`, matched on `mcp__plugin_edakit_easyeda__.*\|mcp__easyeda__.*` | the hook protocol, MCP tool names |
| `edakit/lock.py`, `doctor.py` | the session is `CLAUDE_CODE_SESSION_ID` or the hook's `session_id`; without one nothing is claimed | the EasyEDA claim |
| `skills/new-project/SKILL.md` | writes `.claude/settings.json` (`extraKnownMarketplaces`, `enabledPlugins`) | the project's files |
| `evals/` (7 cases) | the runner `claude plugin eval`; graders `regex`, `tool_used` (`tool: Bash`), a judge | the runner, the transcript `tool_used` reads |
| `README.md`, `handbook/` | "Claude" 10 times in the README, 82 in the handbook; chapter 11 "Working with Claude Code" | words |
| the command line, the checks, `edakit/easyeda/mcp-server.sh` | nothing – stdio MCP for any client | – |

Three tests hold Claude Code's names: `tests/test_references.py` resolves every `${CLAUDE_PLUGIN_ROOT}/…` path,
`tests/test_plugin.py` wants "AskUserQuestion" in new-project and the hook line `python3
"${CLAUDE_PLUGIN_ROOT}/edakit/agreements.py"`. They change with the plugin, on the same branch.

## What the other harnesses read

| Harness | Takes the Claude Code plugin | Skills | Sub-agents | Hooks: session start / before a tool | MCP tool names | Question tool | Headless | Local models |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Code | – | the plugin's, `.claude/skills` | `agents/*.md` | yes / yes | `mcp__plugin_edakit_easyeda__<tool>` | AskUserQuestion | `claude -p`, `claude plugin eval` | – |
| GitHub Copilot CLI (GA 2026-02-25); VS Code 1.143 runs the same runtime by default | yes, as a "legacy plugin": `.claude-plugin/plugin.json` and `marketplace.json`; `enabledPlugins` from `.claude/settings.json` | `.github/skills`, `.claude/skills`, `.agents/skills` | `.github/agents/*.agent.md`, `.claude/agents/*.md`; the `task` tool | yes / yes; PascalCase events get Claude's payloads, matchers and tool names; plugin hooks get `CLAUDE_PLUGIN_ROOT` | the model sees `server-tool`; in hook payloads not documented | `ask_user` | `copilot -p --output-format json` | own key: OpenAI-compatible endpoints, Ollama – the docs' example is `qwen3:8b` |
| Qwen Code 0.26.5 | yes: installs Claude Code marketplace plugins and converts agents, skills, hooks, MCP servers | `.qwen/skills`, `.agents/skills`, configurable | `.qwen/agents/*.md` | yes / yes, Claude Code's events and matchers | `mcp__<server>__<tool>` | `ask_user_question`, Claude's schema; refuses in plain `-p` | `qwen -p` | OpenAI, Anthropic, Gemini protocols; Ollama, vLLM, LM Studio |
| Mistral Vibe 3.0.4 | in part: skills, commands, `.mcp.json`; agents not, a plugin's hooks "not supported yet" | `.agents/skills`, `.vibe/skills` | TOML in `.vibe/agents/` | no / yes (`pre_tool` in `hooks.toml`) | `mcp_<server>.<tool>` | `ask_user_question` | `vibe -p` | Mistral's API, llama.cpp |
| OpenCode 1.19 / 2.2 | no | `.opencode/skills`, `.claude/skills`, `.agents/skills` | `.opencode/agents/*.md` | through JS/TS plugins only | `<server>_<tool>` | `question` | `opencode run --format json` | Ollama, LM Studio, vLLM, llama.cpp |
| Goose 1.57 | hooks only (`hooks/hooks.json`, Open Plugins) | `.agents/skills`, `.claude/skills` | `.agents/agents`, `.claude/agents` | observe only / yes | `<extension>__<tool>` | none; MCP elicitation | `goose run --output-format json` | Ollama, LM Studio, vLLM |

`AGENTS.md` is read by Copilot, Qwen Code, Vibe, OpenCode and Goose. No cross-tool standard covers sub-agents or hooks:
Agent Plugins 1.0.0 standardises skills and MCP only and calls "commands, hooks, agents, rules, and LSP servers" too
client-specific; in practice the others accept Claude Code's formats. Copilot's own documentation adds the caveat that
supporting a format "doesn't guarantee that every component works in every harness" – the probe CI.0 is there for that.

## The models

| Model | Weights and licence | Where it runs | Agentic results, who ran them |
| --- | --- | --- | --- |
| Claude Sonnet 5.5 – through Claude Code or Copilot | closed | hosted | Terminal-Bench 4.0 70.6 % (Anthropic, 2026-09-28) |
| Qwen3-Coder-Next, 80B with 3B active | open, Apache-2.0 (per summaries) | local, or Qwen's API | SWE-bench Verified 70.6 to 71.3; Terminal-Bench 2.0 25.8 in Qwen Code, Sonnet 4.5 37.1 in the same report (Qwen, 2026-02-03) |
| Mistral Medium 3.5, 128B dense – Vibe's default | open, modified MIT (per summaries) | Mistral's API; on four GPUs by Mistral's word (per summaries) | SWE-bench Verified 77.6 % (Mistral, per summaries) |
| Devstral Small 2, 24B | open, Apache-2.0 (per summaries) | one GPU; retired on Mistral's API on 2026-03-31 (per summaries) | SWE-bench Verified 56.4 % (SWE-bench team, mini-SWE-agent) |


There is no like-for-like comparison with the current Sonnet; for edakit the comparison that counts is its own evals.
Copilot hosts Claude, GPT, Gemini, Grok, MAI and Kimi models, no Qwen, Llama or Mistral; those reach Copilot through the
user's own key or a local Ollama.

**Self-hosting.** Ollama and llama.cpp run open models on one's own machine and serve them through an OpenAI-compatible
endpoint; vLLM and LM Studio do the same. Copilot CLI finds Ollama's models by itself and needs a model with tool
calling and streaming – the docs' example is `copilot --model local/qwen3:8b` –; VS Code takes a custom endpoint or
Ollama through its extension; Qwen Code takes a `baseUrl`; Vibe has llama.cpp as a built-in provider at
`127.0.0.1:8080/v1`. Which model passes edakit's evals on which hardware is measured, not assumed – the first matrix
runs Qwen3-Coder-Next and Devstral Small 2 self-hosted. A model's licence is the user's matter and can restrict use:
Llama 4's use policy, for one, grants individuals and companies in the EU no rights under its Section 1(a) for its
multimodal models – support, not legal advice, nothing legally guaranteed, without any claim to correctness.

## The proposal

### Two routes

**The plugin, made portable** – for the harnesses that take it: Copilot (CLI and VS Code), Qwen Code, and Vibe for
skills and MCP. One plugin, one marketplace, one source; each harness installs it its own way.

**Project files, generated from the plugin** – for what a harness does not take from it: the working agreements as a
marked section of `AGENTS.md` where there is no session-start hook (Vibe); sub-agents in Vibe's TOML; and for OpenCode,
which takes no plugin, the skills into `.agents/skills`, the sub-agents into `.opencode/agents/` with `mode: subagent`,
the EasyEDA server in `opencode.json` with `codemode: false` – so that its tools stay single tools a hook sees, not
calls inside Code Mode's one tool –, and a small TypeScript plugin in `.opencode/plugins/edakit/` that calls `edakit
lock hook` before an EasyEDA tool (`ctx.tool.hook("execute.before")`) and adds the working agreements to the session
(`ctx.session.hook("context")`), for OpenCode 2. Goose when a user asks. `edakit assistant <name> --write` writes them,
`--check` reports drift, as `edakit graph json --check` does for the graph; `[project] assistants = ["claude",
"copilot"]` in edakit.toml names a project's harnesses, new-project asks for them, and the check runs in the pre-commit
hook and CI. A harness's configuration then is text in the project's repository, written from edakit's – the yardstick.

### What changes in the plugin

Each change with its test, the plugin working in Claude Code as before:

1. **Paths.** The 18 reads of `${CLAUDE_PLUGIN_ROOT}/handbook/…` become `edakit handbook <section>` – the section alone,
   which also spares a smaller model's context –, the other 9 `edakit root`. in Claude Code these paths work today,
   Copilot documents no expansion in a skill's text; `tests/test_references.py` resolves the new forms.
2. **The MCP server's start.** Copilot documents `${PLUGIN_ROOT}` for a server's arguments, Claude Code uses
   `${CLAUDE_PLUGIN_ROOT}`; the start line takes a form both expand – which one, CI.0 finds out.
3. **The claim's hook.** `lock.py` recognises EasyEDA's tools by their own name (`easyeda_…`) under every harness's
   prefix – `mcp__plugin_edakit_easyeda__`, `mcp__easyeda__`, `easyeda-`, `mcp_easyeda.` …–, the matcher widens with it;
   the hook command keeps the environment variable Copilot also sets. No wrapper around easyeda-mcp-pro – CLAUDE.md
   allows no self-extended MCP server.
4. **The session.** `lock.py` and `doctor.py` read `EDAKIT_SESSION`, then `CLAUDE_CODE_SESSION_ID` and the session field
   of the harness's hook input.
5. **The question tool.** decision-round and new-project name the tool by what it does and list each harness's name –
   AskUserQuestion, `ask_user`, `ask_user_question`, `question` –; the written list stays the fallback ("Without the
   tool the list alone, answered in writing"), and it is what a headless run gets.
6. **The browser.** cart and release name, beside Claude in Chrome, Chrome DevTools MCP with `--autoConnect` – the
   user's running Chrome, after a permission dialog – or the harness's own browser. The skill's rules stay: it never
   orders and never pays, and `edakit cart check` holds what comes back against the job and the release, whichever
   browser filled the form.
7. **The agents' tools.** Tool names every harness here accepts (Bash, Read, Edit, Write, WebFetch, WebSearch …); the
   EasyEDA tools in the form CI.0 shows Copilot and Qwen Code to map.
8. **new-project** writes a harness's settings beside `.claude/settings.json` for each entry of `[project] assistants` –
   Copilot reads `enabledPlugins` and `extraKnownMarketplaces` from that file already.

### What moves into the command line

`edakit handbook` and `edakit root` (above); `edakit agreements --write FILE | --check`, the digest the SessionStart
hook prints today as a section of an instructions file; `EDAKIT_SESSION` for the claim; `EDAKIT_CALL_LOG`, every edakit
command appending its arguments, for the evals.

### Evals for every pair

The cases and their graders stay. A runner `evals/run.py --harness H --model M` scaffolds as today, runs the harness
headless – `copilot -p`, `qwen -p`, `vibe -p`, `opencode run` – and grades: `regex` on the files and the last message;
`tool_used` from `EDAKIT_CALL_LOG` instead of a transcript each harness writes differently; the judge with one fixed
model, so that pairs compare. `claude plugin eval` stays the runner for Claude Code. One case is added because the loops
are what edakit hands the model: a seeded fault fixed until `edakit gate` passes P, G and E – going back after a failed
stage. A pair is **supported** when it passes every case in two of three runs; the README lists the supported pairs with
the date and edakit's version, and a pair that passes the offline cases but not the loop as limited.

The first matrix: Copilot with Claude Sonnet and with a GPT model; Copilot and Qwen Code with Qwen3-Coder-Next
self-hosted through Ollama; Vibe with Mistral Medium 3.5 through Mistral's API and with Devstral Small 2 self-hosted
through llama.cpp; OpenCode with Qwen3-Coder-Next self-hosted through llama.cpp.

### What stays on Claude

edakit's own development – the sessions in this repository, CLAUDE.md, `.claude/skills/`, the Action proposals on the
owner's credentials – stays as it is, and the pipeline's rules are not touched. The checks, the tool chains and the data
are the same for every harness.

## Steps

| Step | What | Size | Waits for |
| --- | --- | --- | --- |
| CI.0 | Probe, before anything is built: the plugin as it is, in Copilot CLI, Qwen Code and Mistral Vibe at once (decision 1), and OpenCode with its files set by hand; add-led, fault-motors, a decision round and the hooks, each with a hosted and a self-hosted model; what breaks is the list for CI.1 and CI.4 | S | the confirmation |
| CI.1 | The plugin portable: items 1 to 5, 7 and 8 above, each with its test; `edakit handbook`, `edakit root` | M | CI.0 |
| CI.2 | `edakit agreements --write\|--check`, `EDAKIT_CALL_LOG` | S | – |
| CI.3 | The eval runner across harnesses, the loop case, the first matrix | M | CI.1, CI.2 |
| CI.4 | `edakit assistant vibe\|opencode --write\|--check` – Vibe's agents as TOML and the agreements in `AGENTS.md`; OpenCode's skills, sub-agents, MCP entry and TypeScript plugin – alongside CI.1; Goose when a user asks | M | CI.0 |
| CI.5 | The browser for cart and release (item 6) | S–M | CI.1 |
| CI.6 | new-project asks for the assistants; project-surveyor reports a harness's files a project brings | S | CI.4 |
| CI.7 | The documentation: chapter 11 with the table of harnesses, the README's supported pairs, the glossary's "assistant", the first property of "edakit as a meta-harness" (documentation.md, decision 14) | S–M | CI.3 |

## Costs and risks

- **Moving targets.** The harnesses change their formats every few months, and Copilot's documentation itself warns that
  a supported format does not mean every component works. CI.0 before CI.1, a test per adapter, and an adapter whose
  harness changes and nobody uses is dropped.
- **Weaker models.** The checks catch a wrong result; they do not catch a model that stops early, loops, or misreads a
  finding. edakit lowers what the model must know about circuits, not what it must do as an agent over a long run. The
  evals show it, and a pair that fails is not listed.
- **The claim.** Every harness in the table can stop a tool call before it runs – Claude Code, Copilot, Qwen Code, Vibe
  and Goose with a hook, OpenCode through a plugin –, so the claim can follow; where a hook does not see an MCP call
  (OpenCode 2 routes MCP tools through one tool, `execute`, unless a server sets `codemode: false` – the generated entry
  does), parallel sessions can collide on EasyEDA. The edakit commands still claim. A documented limit.
- **Data and cost.** A cloud harness sends the project's files to its provider; a local model keeps them on the machine
  and needs the hardware. The choice is the user's, and the documentation says what goes where.
- **Licences.** edakit bundles no model; the model's licence is the user's matter, and what the documentation says about
  it is information, not legal advice.
- **The owner's tokens.** CI.0 to CI.7 are about eight sessions, CI.4 one more per further harness.

## Decisions

Decisions 1, 2 and 4 taken by the owner on 2026-11-01 in a decision round in Claude Code's form; the rest decided by
Claude on the owner's word – "we are writing a concept … details … make a proposal" – and confirmed by the owner the
same day.

| # | Question | Recommendation | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | The order | Copilot (CLI and VS Code) – it takes the plugin, the owner works in VS Code, and it reaches local Qwen through the user's key –; then Qwen Code; then Mistral Vibe; OpenCode and Goose when a user asks | Qwen Code first, the closest to Claude Code; all at once | the owner's choice: all at once – Copilot, Qwen Code and Mistral Vibe in parallel; Copilot first was recommended and not taken; OpenCode added by the owner the same day |
| 2 | The approach | the plugin made portable, project files generated where a harness does not take it | a generated copy per harness; a separate plugin per harness | accepted |
| 3 | Paths in the skills | `edakit handbook` and `edakit root` for every harness, Claude Code included – one plugin | keep `${CLAUDE_PLUGIN_ROOT}` and hope the others expand it | decided by Claude on the owner's word: `edakit handbook` and `edakit root` for every harness – confirmed |
| 4 | "Llama" | read as Meta's model; the owner meant self-hosting – "I mean the LLM self-hosting, not the LLM itself" | – | self-hosting in scope, through Ollama and llama.cpp in all three harnesses, other runtimes through an OpenAI-compatible endpoint; Meta's Llama models not in scope |
| 5 | "Supported" | every case in two of three runs | three of three; a table of results without a threshold | decided by Claude: every case in two of three runs – confirmed |
| 6 | The claim | `lock.py` recognises EasyEDA's tools under every harness's naming | a matcher list per harness | decided by Claude: `lock.py` recognises EasyEDA's tools under every harness's naming – confirmed |
| 7 | A project's harnesses | `[project] assistants` with generated, checked files | per person, untracked | decided by Claude: `[project] assistants` with generated, checked files – confirmed |
| 8 | The words | "the assistant" for the role, the harness by name where it is meant – changes decision 4 of documentation.md and the first property of "edakit as a meta-harness" to "built on an agent harness, Claude Code first" | as today | decided by Claude: "the assistant" for the role, the harness by name – confirmed |

Decided by Claude besides, and confirmed: "all at once" are the harnesses the owner named – Copilot, Qwen Code, Mistral
Vibe, and OpenCode since the owner's addition –, Goose when a user asks; OpenCode through project files and a TypeScript
plugin for OpenCode 2, the EasyEDA server with `codemode: false`; Ollama and llama.cpp are the self-hosting runtimes the
evals run first.

## Sources

- edakit at `e4b82a0`: `.claude-plugin/`, `skills/`, `agents/`, `hooks/hooks.json`, `edakit/agreements.py`,
  `edakit/lock.py`, `edakit/doctor.py`, `evals/`, `tests/test_plugin.py`, `tests/test_references.py`, CLAUDE.md.
- GitHub Docs, read from github/docs at `33b1f4a` (2026-10-31):
  copilot/reference/copilot-cli-reference/cli-plugin-reference, cli-command-reference, cli-programmatic-reference;
  copilot/reference/hooks-reference; copilot/reference/custom-agents-configuration;
  copilot/concepts/customizations/agent-skills; copilot/how-tos/copilot-cli/customize-copilot/add-llm-models;
  copilot/reference/ai-models/supported-models. github/copilot-cli, changelog.md (latest entry 2026-10-27).
- VS Code docs, read from microsoft/vscode-docs at `5a54a29` (2026-10-30): agents/run/agent-harnesses,
  agent-customization/agent-plugins, agent-customization/hooks, agents/run/browser-tools; release notes 1.108 to 1.143.
- Agent Skills: agentskills.io/specification (2026-08-04) and /clients (2026-08-09); agents.md (2026-03-12); Agent
  Plugins 1.0.0, github.com/agentplugins/agent-plugins-spec (2026-07-24).
- Qwen Code at `cea3331` (2026-11-01): README, docs/users, packages/core/src/extension/claude-converter.ts,
  askUserQuestion.ts. OpenCode, github.com/anomalyco/opencode at `4f3156a`. Goose, github.com/aaif-goose/goose at
  `b23d21c`. Mistral Vibe, github.com/mistralai/mistral-vibe at `338ad4b`: README, CHANGELOG.md,
  vibe/core/plugins/_claude.py. Chrome DevTools MCP, github.com/ChromeDevTools/chrome-devtools-mcp (2026-10-30).
- Models: meta-llama/llama-models – the Llama 4 USE_POLICY (its clause on the EU); SWE-bench, data/leaderboards.json
  (2026-09-01); Qwen3-Coder-Next technical report (2026-02-03); anthropic.com/news/claude-sonnet-5-5 (2026-09-28). Per
  search summaries only, not read: Mistral Medium 3.5 and the Devstral models (mistral.ai, docs.mistral.ai), Qwen's
  licences, Meta's Muse models.
