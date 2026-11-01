# Working on edakit

For sessions that change edakit itself – code, catalog, domains, handbook, skills, agents. The plugin's SessionStart
hook adds the working agreements of handbook 11.4 only in a project with an edakit.toml, so not here; they hold here
too.

What is documentation, what is a source, and what a review of the documentation may change:
`docs/organisation.md`.

## The yardstick

Circuit design as code: everything needed to create, edit and change a circuit is text in the project's repository,
and every step can be done by an LLM (`docs/concepts/done/design-as-text.md`). EasyEDA Pro as a desktop program with
its MCP bridge is fine, and the clicks left will go in time; headless builds and CI are not the goal and no argument
for a feature. When weighing a feature or a concept, say whether it leaves something that exists only in EasyEDA or
only in someone's head.

A requirements file covers the circuit only; what firmware and mechanics must do stays in the projects' own documents
(`docs/concepts/done/requirements.md`, decision 3).

## Concepts and branches

- **A concept goes on main.** A concept the owner asks for goes into `docs/concepts/new/` next to the others, not onto
  a branch of its own – the owner follows the repository on GitHub, and a branch is not "in the repository". A concept
  written against an older main is checked against the current one first. It gets there through the notes lane, and
  so does every change of TODO.md, a ticked todo included: `python3 .github/notes.py "<message>" <files…>`, from any
  worktree on any branch, in the background – it lands the session's own edits on the newest main without an OK and
  is merged in about a minute (`docs/concepts/done/versioning.md`).
- **A concept moves on once it is settled.** Decided and built in edakit – what is left being live runs, probes at a
  maker or a project taking it over, each kept in `TODO.md` or the implementation plan –, it moves to
  `docs/concepts/done/`; one the owner rejects moves to `docs/concepts/discarded/`, with the decision in its status
  line. `docs/concepts/new/` holds only what is open, and every link and path that names a moved file follows it.
- **Everything else goes through a branch**, and onto main only with the owner's OK.
- **A merge is a version** (`docs/concepts/done/versioning.md`). A branch that changes what a project reads – anything
  outside `NO_VERSION` of `.github/versions.py`: tests, CI, `evals/`, `docs/`, `examples/`, `upstream/`, `.claude/`,
  TODO.md, CLAUDE.md, README.md – carries a fragment `changes/<branch>.md` (`changes/README.md`): `minor` when a
  project must act when it updates, with what to do, `patch` otherwise – a new rule, a new feature, a fix. The major
  number is the owner's. Such a branch goes onto main as a pull request through `python3 .github/merge.py <n>`, never
  by a local merge: the script numbers it, waits for the checks and merges, and `release.yml` sets the tag. Concepts
  and TODO.md go through the notes lane and are no version.
- **main is protected** by the rulesets in `.github/rulesets/`: nothing reaches it but a pull request with the checks
  test, kicad, build, paths and version green, no force push, no deletion, no bypass, and a version's tag is never
  moved. Every session acts as the owner's account, so this guards against slips and the Actions – the owner's OK for
  code stays the rule above. A refused push to main ("Repository rule violations") moves its commit to a branch; no
  merge needs `--admin`, and none uses it. `python3 .github/rulesets.py` shows whether GitHub has what the files say; a
  change to them is a pull request, applied after its merge with `python3 .github/rulesets.py apply` on the owner's
  word.
- **No branch is left lying around.** When a piece of work is done, list the unmerged branches – local, origin,
  worktrees, and the clones of other sessions, read only. Merge what is finished, rebased and with the tests green, or
  say why a branch of your own stays: waiting for a decision, unfinished. Someone else's branch is one line naming the
  session that holds it – its decisions and OKs are that session's to ask, never an item for the owner in your reply.

## EasyEDA Pro and easyeda-mcp-pro

The owner's rules of 2026-11-01, kept with the requirements in `upstream/README.md`: no click in EasyEDA Pro because
its API gets something wrong or leaves it out – every click edakit asks for is a requirement E-… there until the API
takes it over –; no self-extended MCP server – no new patch of easyeda-mcp-pro, what edakit needs goes upstream as an
issue and a pull request from the fork tgd1975/easyeda-mcp-pro –; and before a requirement is reported, a branch built
or a workaround changed, the latest state upstream is checked ("The latest state" there). A new click, patch or
workaround goes into that list in the same commit.

## Proposals

The Action proposals runs Claude on the owner's own credentials (`CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`):
every run is paid by the owner, so nobody else may start one or flood it with proposals. The job `queue` of
`.github/workflows/proposals.yml` lets only the owner's own sealed issues, the owner's answers on them, and on an issue
by someone else the owner's sealed comments and commands `review` and `accept` through, before any Claude step runs,
and its queue lists only the owner's issues (`--author`) and those the owner adopted; the triage skills stop once more
at an issue by anyone else that the owner did not adopt. Keep both. Never loosen the job's `if` or the queue's
`--author`, never leave the check to the prompt or a skill alone – a check inside Claude's run has spent the tokens
already –, and do not suggest another trigger or a condition others can meet without being asked.

The one workflow others start is `.github/workflows/wrap.yml`, on the owner's word: it wraps their texts with a fixed
Python step and closes an issue on the owner's `reject` – no Claude, no secret, only `contents: read` and `issues:
write`. Keep it so; a test holds it.

The owner's decisions of 2026-11-01 (`docs/concepts/done/proposals-pipeline.md`):

- **One further start:** a comment by the owner carrying the seal, on an issue by someone else – the workflow labels
  it `adopted`, and Claude reads only the owner's comments and the triage's results there. A condition only the
  owner meets.
- **Texts by others are wrapped, the owner answers with a command** (decisions 7 to 9): on an issue by someone else
  every text the owner did not write is posted again by `wrap.yml` – plain text in a code block, numbered within the
  issue, sealed; an edited one again under a new number. The owner's comment that starts with `review` (a judgement,
  no build), `accept` (the build) or `reject` (closed at once, without Claude) is the only answer that starts
  anything there; Claude reads only the wrapped texts that came before the command. Wrapping and commands hold on
  issues by others only.
- **Claude only reads.** In the pipeline its token cannot write; it commits locally and writes its result as files.
- **A fixed job checks the commit** against the pipeline's paths before anything is pushed – the list lives once, in
  `edakit/proposal.py`.
- **The pipeline is never changed through itself.** A proposal that touches one of those paths, or how proposals are
  started, read, judged, built or published, is rejected; a change of the pipeline comes from a session on the owner's
  word.

Proposals come from projects only when the owner asks (plugin skills `skills/propose-rule` and
`skills/propose-feature`); the triage (`.claude/skills/triage-rule`, `triage-feature`, for requests by others
`triage-request`) builds accepted ones into one pull request each, and the owner merges. Never file an issue or a proposal on your own, and do not suggest dropping
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
