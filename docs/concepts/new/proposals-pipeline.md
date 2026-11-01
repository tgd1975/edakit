# The proposals pipeline: checked before it acts, never changed through itself

Status 2026-11-01: decided – the five decisions accepted by the owner the same day in a decision round in Claude Code's
form, and a sixth on the owner's addition: issues by others are welcome, and the owner hands one to the pipeline with a
sealed comment (the table at the end); the steps start on the owner's word. Asked for by the owner after a review of the
pipeline: the pipeline can change anything, so every incoming issue is analysed closely – is it from an authorised
person (today the owner alone), is it correctly formatted, is it plausible, is it acceptable, is it dangerous, does it
change this pipeline. The last is an absolute no-go: the pipeline must never be changed through itself. Aligned before
it was written, on the owner's word: with edakit-93, which built the fixes of the day (702a4f4, 7a20a13, a7a1337),
merged the proposals pull requests #89, #96, #101 and #102 and handed the pipeline over; and with edakit-a3, whose
concept `versioning.md` proposes the rulesets on main and a required check of the paths per branch family – this concept
names the paths the proposals branches never touch and leaves the rulesets to it. Written against main at `557dc01`.

## The short answer

Today the six checks stand mostly in a prompt. Who may start the pipeline is fixed in the workflow; everything else –
the format, what a proposal may change, and above all that it never changes the pipeline – is Claude's judgement while
Claude holds a token that can write to every branch, main included, and very likely change workflows. The proposal
splits the pipeline into four layers: GitHub keeps main for the owner; fixed steps before Claude check who and the
format and give Claude only the owner's text and main's rules; Claude judges in the owner's order and only reads; a
fixed job after Claude checks the commits against the pipeline's paths before anything is pushed. Four faults of the
day go with it: a proposal triaged twice, a commit lost when a pull request is merged during a build, a run that ends
green without a result, an answer lost when it is given by sealing again. Issues by others stay welcome; the owner
hands one to the pipeline with a sealed comment, and only that comment reaches Claude.

## The state today

| The owner's check | Where it is today | Fixed or judged |
| --- | --- | --- |
| From an authorised person | the job `queue`: its `if` (sender and author the owner, the seal's marker) and `gh issue list --author` | fixed – but Claude reads every comment of the issue, others' too; only the prompt says to ignore them |
| Correctly formatted | `edakit proposal verify`, step 1 of the triage skills | judged: Claude runs it, and a broken proposal costs a Claude run to get its question |
| Plausible | the triage table: new, the sources hold, the gap real | judged |
| Acceptable | the triage table: the right kind, general, fits edakit, graded by the purpose, clear | judged |
| Dangerous | – | no check of its own |
| Changes the pipeline | – | neither checked nor prevented |

What makes the last row serious:

- **main is open.** No branch protection, no ruleset (the API, 2026-11-01). The skills say "never to main"; nothing
  else stops a push or a merge into it.
- **Claude holds the Claude App's token.** The action exchanges an OIDC token for it (`id-token: write`; the log of
  run 41298019722: "Exchanging OIDC token for app token"). The App asks for `contents`, `workflows`, `actions` and
  `repository_hooks` write (its manifest, `/apps/claude`). A push with it starts workflows, and a workflow it adds runs
  with the repository's secrets. The sentence in the body of #101 that the App may not push a workflow change was the
  triage's assumption; its log shows no push that was refused.
- **The rules come from the branch.** Step 4.1 of the triage skills checks out the proposals branch, step 4.2 follows
  the SKILL.md of add-rule or add-feature – the branch's copy. What one triage commits there steers the next one
  before anyone has read it.

## What went wrong on 2026-11-01

1. **Triaged twice, since a7a1337.** The queue puts the issue that started the run first, always
   (`proposals.yml:80`) – also when an earlier run took it along and answered it. Before a7a1337, Claude's own
   comments started runs that replaced the last waiting one and hid this. The morning's batch shows it: the run of #90
   took #90 to #95 along; under today's workflow the waiting run of #95 would have started at 09:09 and triaged #95 a
   second time. A triage costs a paid run – 1.77 to 3.41 USD today as the action counts it, 53 to 84 turns.
2. **A commit without a pull request.** #89 was merged at 10:44 while the triage of #99 (the layers picture) was
   building into its branch; the commit 166b847 came after the merge, and the comment named #89. edakit-93 carried it
   on by hand in #101. A triage that finds no open pull request starts the branch new from main and pushes with
   `--force` – the commit would have been gone.
3. **Green without a result.** The triage of #94 at 10:15 ended after 78 turns (2.85 USD) without its comment; why is
   not known. The step *Why Claude stopped* (7a20a13) shows it from now on.
4. **An answer by sealing again.** A proposal sealed again after a question is not in the queue's list of waiting
   proposals – its last comment is still the question. If its own run is replaced while it waits, it is lost.
5. **One condition, written twice.** The concurrency group and the job's `if` hold the same eight lines; they are
   equal today, nothing keeps them so.

## The proposal

### Four layers

| Layer | What | Enforced by |
| --- | --- | --- |
| 1 GitHub | only the owner changes main; Claude works without a token that can write | the rulesets of `versioning.md`; the workflow's own token |
| 2 Before Claude | who, the format, the text Claude gets, the rules it follows, the branch | fixed steps of the workflow, main's code |
| 3 Claude | safe, plausible, acceptable – then the build, committed locally | the triage skills, a token that only reads |
| 4 After Claude | the commits against the pipeline's paths; push, pull request, comment, labels | a fixed job, main's code |

Layers 1, 2 and 4 hold whatever a proposal says and whatever Claude does; layer 3 is the judgement only Claude can make.

### Layer 1: GitHub

- **main.** The rulesets of `versioning.md` (edakit-a3): only the owner updates main, and a required check holds
  `rules/*` and `features/*` off the pipeline's paths. Run on `pull_request_target` – main's workflow and list –, it
  reads only the list of changed files; a `pull_request` run would use the branch's own copy of the check.
- **The token.** The triage runs with the workflow's own token and the permissions each job names, without
  `id-token: write` – the App's token is never fetched. The workflow's token cannot change a workflow file, and what it
  pushes starts no workflow. It needs the setting "Allow GitHub Actions to create and approve pull requests"; once the
  pipeline ran with it, the Claude App can be uninstalled.

### Layer 2: before Claude

- **Who.** The issue's author is the owner, read again from the API, not from the event. The text Claude gets is a
  file with the body, the owner's comments and the triage's earlier results – nothing others wrote.
- **The format.** `edakit proposal verify` with main's `edakit/proposal.py`. If it fails, the workflow posts the
  **Question** with what verify reports and labels the issue `needs-info`; Claude does not start.
- **The rules.** The skills triage-rule, triage-feature, add-rule and add-feature are copied from main before the
  branch is checked out; the prompt names the copies.
- **The branch.** The branch of the open pull request, or a new one from main – with the commits a merged pull request
  left behind picked over, never overwritten.

### Layer 3: Claude judges

In the owner's order, with one change: the dangerous and the pipeline come first, because such a proposal is rejected
however plausible it is, and no question goes back to it. The first check that fails decides.

1. **Safe?** **Rejected**, never a question, when the proposal would
   - change the pipeline: one of its paths (below), or how proposals are started, read, judged, built or published;
   - run or fetch at check time what edakit does not run today – the network, a command, code or files the proposal
     names;
   - read credentials or write outside the project;
   - add a hook, skill, agent or setting that acts without the user's word – push, order, pay, publish, permissions;
   - weaken a check – a lower severity, a retired code, a looser limit – without a source that shows the check wrong;
   - need a new dependency (`pyproject.toml`, `uv.lock`) – the owner adds it by hand, then seals the proposal again.
2. **Plausible?** The rows of today: new, the sources hold, the gap real at this commit.
3. **Acceptable?** The rows of today: the right kind, general, fits edakit, graded by the purpose, testable, one
   capability, clear enough to build.

Accepted, Claude builds as add-rule or add-feature say, commits once on the branch of layer 2 and writes three files:
the result, the comment, the line for the pull request. It pushes nothing, comments nothing, labels nothing – its token
only reads.

### Layer 4: after Claude

A job of its own, with the write permissions, and nothing but fixed steps:

- **The commits.** At most one, on the branch of layer 2, its message ending in `(#N)`, touching none of the
  pipeline's paths. Else nothing is pushed: the job posts **Rejected** – the build touches the pipeline, with the
  paths – and labels the issue.
- **The pull request, asked again** right before the push. Merged meanwhile: the commit is rebased onto main and goes
  into a new one.
- **Then** the push, the line in the pull request, the comment, the labels, closing a rejected issue – and the pull
  request's tests, started by the job: what the workflow's token pushes starts no workflow by itself (`tests.yml` gets
  `workflow_dispatch`).
- **No result file** – the green run of #94 – posts nothing; the proposal stays waiting, and the job fails, so the run
  shows red.

### The pipeline's paths

`.github/` · `.claude/` · `CLAUDE.md` · `edakit/proposal.py` · `tests/test_proposal.py` · `skills/propose-rule/` ·
`skills/propose-feature/` · `pyproject.toml` · `uv.lock` – the workflows, the repository's skills, the rules for
sessions, seal, verify and the queue with their tests, how proposals are written, what the jobs install and run. The
list lives once, in `edakit/proposal.py`, pinned by a test; layer 4 and the check of `versioning.md` read it from main.

### The queue

- **The issue that started the run** goes first unless a triage answered it after its event – for every event alike:
  filed, answered, sealed again, reopened. A run that waited behind the one that took its proposal along triages
  nothing.
- **Waiting** is a proposal without a result, or with a question the owner answered since – in a comment or by sealing
  it again (the body's last edit, by the owner, after the question; GraphQL `lastEditedAt`).
- `gh issue list --author` stays as `CLAUDE.md` names it. The logic moves into `edakit/proposal.py` with its tests; a
  test holds the concurrency group equal to the job's `if`.

### Issues by others

An issue by someone else is welcome – the pipeline only does not act on it by itself. The owner hands it over with a
sealed proposal as a comment there: the owner's session writes the proposal from the issue with propose-rule or
propose-feature, seals it and posts it (`gh issue comment N --body-file body.md`).

- **The start.** Beside today's conditions, the job's `if` lets in a comment by the owner that carries the seal, on any
  issue that is not a pull request – a condition only the owner meets. The workflow labels the issue `adopted`; from
  then on the owner's answers there start the pipeline as on the owner's own issues.
- **What Claude reads** is the owner's newest sealed comment as the proposal, the owner's comments after it and the
  triage's results – never the body of the issue or a comment by anyone else. What its author edits later changes
  nothing.
- **The queue** lists, beside the owner's own proposals, the open issues labelled `adopted` whose newest sealed comment
  by the owner has no result after it.
- **The result** is a comment on that issue, and the pull request closes it like any other.

### One proposal after another

Claude reads and a fixed job writes: two jobs per proposal, and the next triage starts after the publish of the one
before, because accepted proposals share their branch. A matrix cannot interleave two jobs, so the run calls a reusable
workflow – triage, publish – once per proposal in the queue, each call waiting for the one before, at most eight per
run; the rest stays waiting for the next run.

## Steps

| Step | What | Size | Waits for |
| --- | --- | --- | --- |
| P.1 | The queue in `edakit/proposal.py` with tests: the trigger only if unanswered since its event, sealing again as an answer, the adopted issues of others; the test that holds the concurrency group equal to the `if` | S | the decisions |
| P.2 | The pipeline's paths and the check of the commits in `edakit/proposal.py`, with tests; the file with the owner's text only – on an adopted issue the owner's sealed comment | S | the decisions |
| P.3 | `proposals.yml` and the reusable `proposal.yml`: the queue, the chain, the start by the owner's sealed comment and the label `adopted`, the triage (the reading token, verify, the skills from main, the branch, Claude), the publish (the check, the pull request asked again, push, comment, labels, the tests started); `workflow_dispatch` for `tests.yml` | M | P.1, P.2 |
| P.4 | The triage skills: the checks in the owner's order, "Safe?" first; three files instead of push, comment and labels; an adopted issue read from the owner's comment. propose-rule and propose-feature: a proposal from an issue by someone else, posted there as a comment. add-rule and add-feature: the line on pushing | S | P.3 |
| P.5 | Handbook 14.4 (the checks, the layers, what happens before a merge, issues by others welcome), 11.6, 10 (`verify FILE\|-`); `README.md` (the kinds of a rule proposal, the link to 11.6); the section Proposals of `CLAUDE.md` (the owner's sealed comment on an issue by someone else, decision 6); `docs/organisation.md` | S | P.4 |
| P.6 | The setting for pull requests, on the owner's word; then live: two sealed test proposals by the owner – a harmless one, and one that asks to change triage-rule, which must end rejected without a push | S | P.5, the owner |
| P.7 | The Claude App uninstalled | – | P.6, the owner |

One branch for P.1 to P.5, about one session; onto main with the owner's OK, after a notice to the sessions.

## Alternatives

- **Claude keeps write access, a check after its push** resets the branch. One job per proposal and simpler, but what
  Claude pushed is on GitHub before the check runs, and with the App's token its pushes start workflows.
- **A rule for whoever merges** (edakit-93): never while a proposals run builds. No code, but a session can forget it;
  asking again before the push makes it unnecessary.
- **The trigger only while it is still waiting** (edakit-93): needs cases of its own for sealing again and for a
  reopened proposal; "unless answered since its event" covers every event alike.
- **One proposal per run**, the publish starting the next by dispatch: the job's `if` would have to let in a run the
  workflow started itself – a loosening `CLAUDE.md` forbids.

## Costs and risks

- **What no layer catches:** harmful code in edakit itself inside an accepted proposal. The owner's review of the pull
  request stays the last gate (`CLAUDE.md`).
- **The action with a token that only reads** is to be probed in P.3 – likely, and if it needs more to start, the
  triage job gets exactly that, never `contents: write`.
- **A proposal that needs a new dependency** is rejected and goes by hand – rare, then ten minutes.
- **Comments and pull requests** come from `github-actions[bot]` instead of `claude[bot]`.
- **A new file of the pipeline** must join the list – the test names the list.
- **More jobs per proposal:** the publish job adds about a minute.

## Decisions

Taken by the owner on 2026-11-01, in a decision round in Claude Code's form; "accepted" is the owner's yes to the
recommendation. Decisions 3 and 4 were asked as one question.

| # | Question | Recommendation | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | How the six checks are held | the four layers: who and the format fixed before Claude; Claude judges safe, plausible, acceptable and only reads; a fixed job checks the commits against the pipeline's paths before anything is pushed | Claude keeps write access and a check runs after its push; as today | accepted |
| 2 | The token | the workflow's own token, no `id-token: write`; the setting for pull requests on; the Claude App uninstalled after P.6 | the Claude App stays | accepted |
| 3 | The pipeline's paths | the nine above | also `hooks/` and `.claude-plugin/` – what runs in projects without being asked; fewer | accepted |
| 4 | What counts as dangerous | the six kinds of "Safe?", each rejected | each a question; fewer kinds | accepted |
| 5 | The queue | the trigger unless a triage answered it since its event; sealing again counts as an answer | the trigger only while it is waiting, with cases for sealing again and reopening | accepted |
| 6 | Issues by others (the owner's addition: "issues by others are not wrong or unwanted – the pipeline only does not act on them by itself; I start it by hand, perhaps with a comment that starts the pipeline") | welcome; the owner hands one over with a sealed proposal as a comment there, and the pipeline reads only that comment | a plain command `/triage` that reads the issue's text as it stood at the comment; filed again as the owner's own issue | accepted |

Decided by Claude: the chain of at most eight calls and Claude's result as files – both named in the question of
decision 1 and accepted with it; the list and the check in `edakit/proposal.py`, read from main, and GraphQL for the
body's last edit – technical; the rulesets left to `versioning.md`, which takes the list of paths from here; the test
proposals of P.6 are asked for when P.6 is due.

## Sources

- Runs of `proposals.yml` on 2026-11-01: 41284818471 (#90 to #95), 41296659894 (#94, green without a result),
  41298019722 (#99 and #94), 41300609523 (#100, the first with all three fixes); their logs.
- Issues #94, #99, #100; pull requests #89, #101, #102.
- GitHub API, 2026-11-01: `repos/tgd1975/edakit/branches/main/protection` (not protected), `…/rulesets` (none),
  `…/actions/permissions/workflow` (default read, pull requests by Actions off), `/apps/claude` (the App's permissions).
- `.github/workflows/proposals.yml` at `557dc01`; `.claude/skills/triage-rule/SKILL.md`,
  `.claude/skills/triage-feature/SKILL.md`; `edakit/proposal.py`.
- The messages of edakit-93 and edakit-a3, 2026-11-01.
