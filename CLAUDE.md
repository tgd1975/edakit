# Working on edakit

For sessions that change edakit itself – code, catalog, domains, handbook, skills, agents. The plugin's SessionStart
hook adds the working agreements of handbook 11.4 only in a project with an edakit.toml, so not here; they hold here
too.

## The yardstick

Circuit design as code: everything needed to create, edit and change a circuit is text in the project's repository,
and every step can be done by an LLM (`docs/concepts/new/design-as-text.md`). EasyEDA Pro as a desktop program with
its MCP bridge is fine, and the clicks left will go in time; headless builds and CI are not the goal and no argument
for a feature. When weighing a feature or a concept, say whether it leaves something that exists only in EasyEDA or
only in someone's head.

A requirements file covers the circuit only; what firmware and mechanics must do stays in the projects' own documents
(`docs/concepts/new/requirements.md`, decision 3).

## Concepts and branches

- **A concept goes on main.** A concept the owner asks for goes into `docs/concepts/new/` next to the others, not onto
  a branch of its own – the owner follows the repository on GitHub, and a branch is not "in the repository". A concept
  written against an older main is checked against the current one first.
- **Everything else goes through a branch**, and onto main only with the owner's OK.
- **No branch is left lying around.** When a piece of work is done, list the unmerged branches – local, origin,
  worktrees, and the clones of other sessions, read only. Merge what is finished, rebased and with the tests green, or
  say why a branch stays: waiting for a decision, unfinished, someone else's.

## Proposals

The Action proposals runs Claude on the owner's own credentials (`CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`):
every run is paid by the owner, so nobody else may start one or flood it with proposals. The job `queue` of
`.github/workflows/proposals.yml` lets only the owner's own sealed issues and the owner's answers through, before any
Claude step runs, and its queue lists only the owner's issues (`--author`); the triage skills stop once more at an
issue by anyone else. Keep both. Never loosen the job's `if` or the queue's `--author`, never leave the check to the
prompt or a skill alone – a check inside Claude's run has spent the tokens already –, and do not suggest another
trigger or a condition others can meet without being asked.

Proposals come from projects only when the owner asks (plugin skills `skills/propose-rule` and
`skills/propose-feature`); the triage (`.claude/skills/triage-rule`, `triage-feature`) builds accepted ones into one
pull request each, and the owner merges. Never file an issue or a proposal on your own, and do not suggest dropping
the pull request as the last gate.

## Decisions

Open decisions go to the owner as the skill decision-round asks them: real questions in Claude Code's form, each with
its alternatives and the recommendation first, a file named by its path (`hardware/boards/main.toml`, not "the main
file"). What Claude decided itself goes into one closing question for confirmation.

## Regulatory content

- **Not legal advice.** Wherever regulatory content reaches a reader – chapter 15, the agent regulatory-reviewer, M-6
  in the gate protocol, the README, a skill that reports M-6, a new document or concept that touches regulation – it
  says once that it is support, not legal advice, nothing legally guaranteed, without any claim to correctness.
- **Graded by the purpose** (handbook 15.4, the owner's decision of 2026-10-29): what the firmware or a data entry can
  settle is a note for a board built for oneself or given away, a warning for one that is sold, and an error only
  where the hardware cannot comply. A new regulatory code or proposal follows it (add-rule section 5, triage-rule).
