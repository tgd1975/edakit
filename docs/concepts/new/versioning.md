# Versions and branch protection: what a version of edakit is, how main is protected, how a concept still gets there

Status 2026-11-01: decided. The owner took the four decisions the same day in a decision round in Claude Code's form
(the table at the end): 0.2.0 first, with 1.0 once the documentation's entry layer is built; the notes lane; every merge
a version of its own; the projects on the newest version, unpinned. The owner then added three points: a changelog from
now on; the major number is the owner's to release, minor and patch are Claude's; a new rule is a patch, and the rule
for the rest kept simple. What Claude decided itself the owner confirmed the same day. Each step starts on the owner's
word, listed in `TODO.md`. V.1 and V.2 (TD-45) built on the owner's word the same day, on the branch `versioning-v1`;
building them made three things simpler, written in below: the check `changes` is part of `version`, the paths decide
which merge is no version (no fragment `none`), and the working rule for merging went into CLAUDE.md with V.2 rather
than V.4, so that no merge comes past `merge.py` while the rulesets wait. On the owner's word the reader's documentation
came with V.2 too: README (Install, Versions), handbook 2.3, 10.5 (`--version`), 14.4 and the glossary's "Version".
Written against main at `d633a4b`. Asked for by the owner: edakit has reached the point where it should work with
version numbers and branch protection from now on – a concept for both, and, since a concept could then no longer be
committed straight to main, an elegant way for concepts to get there all the same. V.3 (TD-46) built the same day:
`.github/notes.py`, which merges by itself instead of GitHub's auto-merge. V.4 (TD-47) built the same day: the rulesets
and the settings as files with `.github/rulesets.py`, `merge.py` no longer numbering again a pull request without a
version; the line in the four repository skills that writes a fragment per change, one per proposal, follows in a pull
request of its own once the batch of proposals being triaged is through.

## The short answer

Every merge that changes edakit is a version of its own, and its number tells a project whether it has to act. The
owner sets the major number when they release one, 1.0 once the documentation's entry layer is built. Claude sets the
other two by one question: must a project change its files or sign again when it updates? If so, the minor number
goes up, and the changelog says what to do. Otherwise the patch number goes up, for a new rule, a new feature or a
fix.

The number is written in one place, and the merge sets it. One small file per branch says what kind of change the
branch makes, and those files give both the number and the changelog. So parallel sessions never pick a number by
hand and never conflict over the changelog. The marketplace entry points at the newest version's tag. A project
installs that version, and the owner's projects follow it unpinned, as they follow main today.

main gets rulesets that are kept as JSON in the repository. Every change comes through a pull request with green
checks, and `merge.py` merges only while main still has the number it numbered from, so two merges never get the
same number. Nobody may
force-push or delete main, and the owner has no bypass. One fact shapes all of it: every session acts as the owner's
GitHub account. GitHub cannot tell a session from the owner, so the protection guards against slips and against the
Actions. It does not lock out the sessions, and the owner's OK for code stays a working rule.

Concepts and the todo list keep their speed through the **notes lane**. A pull request from a branch `notes/<topic>`
that changes only `docs/concepts/` and `TODO.md` is merged as soon as its checks are green, with no OK needed, as today,
and it is no version. A required check makes sure nothing else slips through that lane. One command lands a session's
edits there from any worktree and any branch, with the checkout left alone. The concept is on main about five minutes
later.

## What is there today

- **No version.** `pyproject.toml` and `edakit/__init__.py` have said 0.1.0 since the first commit. There are no tags
  and no changelog. `.claude-plugin/plugin.json` has no `version`, so Claude Code takes the commit as the version. In
  `~/.claude/plugins/installed_plugins.json` this machine, the bell and pytree all run `8c6652cd52bd`, a merge from
  this morning. That state lives in one machine's cache and nowhere in a repository.
- **Manifests that say nothing.** Every gate run writes `tools.edakit: "0.1.0"` (`edakit/release/gate.py`, `header`).
  So no released board can say which edakit released it.
- **pytree pins in two halves.** Its CI runs the command line at a commit (`hardware/edakit.sh`, its D-50), while its
  plugin, skills and agents follow main. The skills come from one state of edakit and the CLI from another.
- **main is open.** There is no branch protection and no ruleset. Of the 94 merges, most were a local `git merge`
  pushed to main, and pull requests come only from the proposals Action. That Action runs with `contents: write`, so
  only its prompt keeps it off main.
- **Concepts and TODO.md go straight to main.** CLAUDE.md wants a concept on main because the owner follows the
  repository on GitHub. The owner's rule for todos wants an item ticked right away by whichever session learns it.
- **CI on every push and pull request:** Tests (`test` about 5 min, `kicad` about 1 min) and Pages (`build` 15 s,
  which also fails on a broken link).
- **Several sessions at once**, all with the owner's `gh` login and git credentials.
- **The plugin cache holds no `.git`.** `~/.claude/plugins/cache/edakit/edakit/<version>/` holds the files and a
  `.venv`. So a number derived from the tag when the code runs would be missing there, and the number has to be
  written in the tagged commit itself.

## What a version of edakit is

### What a project relies on

These are the parts of edakit a project's files depend on:

- the keys of `edakit.toml`;
- the formats of the graph, the parts entries, the requirements file, the sign-offs and `scripts.lock`;
- the commands and their exit codes;
- the codes of the catalog and their severities;
- the hashes the sign-offs are bound to;
- the seal of a proposal;
- the skills and agents.

### The numbers

Three numbers, major.minor.patch, starting at 0.2.0:

| Number | Set by | When | Examples |
| --- | --- | --- | --- |
| **Major** | the owner | when the owner releases one; Claude may propose it, never set it | 1.0.0 once step D.2 of [documentation.md](documentation.md), the entry layer (start page, quickstart, how it works), is built |
| **Minor** | Claude | a project must change one of its files or sign again when it updates | a key, file format, command or exit code removed or changed in meaning; a hash computed differently (sign-offs void); a retired code that waivers name; a new seal format |
| **Patch** | Claude | everything else | a new rule (check, hint, block, parts fact), a severity raised; a new command, key, maker or skill; a fix; the handbook; a prompt's wording |
| – | the paths | a merge that changes nothing a project reads, the notes lane among them: no version, no fragment | `tests/`, `.github/`, `evals/`, `docs/`, `examples/`, `upstream/`, `.claude/`, `TODO.md`, `CLAUDE.md`, `README.md` |

So a single question settles the number: does a project have to do something when it updates? The rule stays the
same before and after 1.0. A minor version brings a way across with it: `edakit convert` where a format changes, and
in every case lines in the changelog that say what a project does, such as which sign-offs to renew. The
implementation plan already names every hash a step changes. Each such step is a minor version.

The owner releases a major version by naming the pull request: `merge.py <n> --major`.

### Where the number is written

- **One place.** The text `__version__ = "0.2.0"` in `edakit/__init__.py`. `pyproject.toml` reads it from there
  (hatch: `dynamic = ["version"]`, `[tool.hatch.version] path`), so even a checkout that nothing has installed can be
  read, and `pyproject.toml` stays untouched by a version.
- **The marketplace entry** carries `version` and the source `{"source": "github", "repo": "tgd1975/edakit",
  "ref": "v0.2.0"}`. The plugin a project installs is exactly the tagged commit. `plugin.json` stays without a
  version, so that the number is not written twice.
- **A test holds them together:** the entry's version equals the package's, the ref is `v` plus that number, and the
  top section of the changelog has that number.
- **`edakit --version`** prints `0.2.0`. From a git checkout away from the tag it prints `0.2.0+g1a2b3c4`. The gate
  manifest's `tools.edakit` takes the same string, so a manifest names the edakit that released the board, down to
  the commit if it was not a version.

### How a project gets a version

Claude Code keys its plugin cache by version. A plugin is only updated when the version changes, and a running session
keeps the old one until `/reload-plugins` or a new session starts (code.claude.com, plugins: "Version management",
"Host and maintain").

- **The newest version, the default and the owner's projects.** `/plugin marketplace add tgd1975/edakit`, as today.
  The marketplace comes from main, and its entry points at the newest tag. Updating is the same command as today
  (README, Install), and auto-update is off for marketplaces outside Anthropic. Since every merge that changes edakit
  is a version, this is what main is today, now with a number.
- **Pinned, for whoever wants it.** A project sets `"ref": "v0.4.2"` in the github source of
  `extraKnownMarketplaces.edakit` in its `.claude/settings.json`. Its CI runs
  `uvx --from git+https://github.com/tgd1975/edakit@v0.4.2 edakit`. Skills and command line then share one version,
  written in its own repository. The README says how to do it. The owner's projects do not use it.

A second channel for main is not needed. main holds nothing that is not already a version, except concepts and the
todo list. pytree's CI pin to a commit (its D-50) is pytree's own decision. With tags it could name a version instead,
and that is for its session to decide, in its repository.

### The changelog

`CHANGELOG.md` sits at the root, newest version first: a heading with the number and the date, then the lines of
that merge. A minor version's lines begin with **When updating:** and what a project does. It is written for a maker
who updates, not for whoever wrote the code.

It starts now. Its first section, 0.2.0, lists what was merged from 2026-11-01 on, taken from the merge messages,
which already describe each change. Everything before that is 0.1.0, kept in the git history.

Its lines come from **fragments**. Each branch writes one file of its own, `changes/<branch>.md`. The first line is
`minor` or `patch`, and the lines after it are the text for the changelog (`changes/README.md`). The merge turns the
fragments into the version's section and deletes them, so `changes/` on main holds nothing but its README. While
several sessions work at once, every branch writes into a file of its own and none waits for another. A branch that
changes nothing a project reads needs none: the list of those paths is `NO_VERSION` in `.github/versions.py`, and such
a merge is no version, a merge through the notes lane among them.

The required check `version` (below) fails a pull request that changes what a project reads but carries no fragment.
Every proposal that triage accepts adds its own fragment
(`changes/rule-<issue>.md`, `changes/feature-<issue>.md`), a patch unless a project has to act, which is one line
more in the triage skills.

### A merge is a version

edakit's own word "release" already means a board's release (handbook 8, `edakit release`). So this concept speaks of
"a version of edakit" and of "edakit's GitHub release", and the handbook keeps "release" for the board.

The number has to be in the pull request before it is merged. A workflow cannot write it afterwards: main takes
nothing but a merged pull request, a commit by the GITHUB_TOKEN would start no checks, and a second identity is not
proposed (below). So with the owner's OK, a session merges through `.github/merge.py <n>`:

1. It brings the branch onto the newest main. A conflict outside the version's own lines stops it and names the files.
2. It works out the next number from main's number and the branch's fragments: minor if one says `minor`, otherwise
   patch.
3. It writes that number in `edakit/__init__.py` and in the marketplace entry (version and ref), turns the fragments
   into the changelog's new section and deletes them, and commits that as "edakit 0.2.6".
4. It pushes the branch, waits for the checks (about 5 minutes) and merges with `--match-head-commit`, so that nothing
   pushed meanwhile slips in.
5. It merges only while main still has the number it numbered from. A push of `TODO.md` or a concept in the meantime
   changes nothing. A version merged in the meantime does: then the script goes back to step 1, and since it rewrites
   the version's lines anyway, they never conflict.

The workflow `release.yml` runs on every push to main. When the package's number has no tag yet, it sets the tag
`v0.2.6` on that merge commit and opens the GitHub release with the changelog section as its text. A merge without a
version (nothing a project reads) leaves the number alone, and the workflow does nothing. A branch that the proposals
workflow pushes with its own token starts no checks ([proposals-pipeline.md](../done/proposals-pipeline.md) gives it that
token). `merge.py`'s push of the numbered commit comes from the owner's account and does start them, so a proposals pull
request gets its checks at the merge.

A required check `version` guards the button. A pull request that carries fragments is not numbered yet, and the check
stays red with the text "set when merging: `.github/merge.py <n>`". So GitHub's merge button cannot merge a change
without its number. The owner says "merge #102" to a session, as today. A pull request that `merge.py` has numbered
passes the check, provided its number follows main's.

Merges now run one after another, about five minutes each, and `merge.py` runs in the background with a monitor that
reports each step. There are no hotfix branches: a fix is a pull request like any other and a version minutes later.

## Branch protection

### The fact that shapes it

Every session pushes and merges as the owner's account. Any right the owner keeps, every session has too, and any
bypass the owner takes is a bypass for all of them. So the rules below guard against four things:

- a slip, such as a commit on local main or a push of a red branch;
- a force push;
- a change merged without its number;
- the Actions: the proposals pipeline runs Claude with the Claude App and the GITHUB_TOKEN, both with `contents:
  write`.

The owner's OK for code stays a working rule in CLAUDE.md. A real lock would take a second identity for the sessions,
a GitHub App or a machine account, plus a required approval from the owner on every pull request. That is not proposed
now: it costs an identity handed to every session and a click on GitHub for each merge, against a risk the working
rule has handled so far. The option stays open.

### The rules, as text

The files sit in `.github/rulesets/` – one per ruleset, and `settings.json` for the merge settings. They are applied
with `python3 .github/rulesets.py apply`, and without `apply` the script shows what differs between the files and
GitHub. The protection is then text in the repository like everything else. A change to it goes through a pull
request and is applied after the merge, on the owner's word.

| Ruleset | Target | Rules | Bypass |
| --- | --- | --- | --- |
| `main` | main | a pull request, no approval required (the owner cannot approve their own, and the sessions are the owner); the checks `test`, `kicad`, `build`, `paths` and `version` green, not strict; no force push; no deletion | nobody, the owner included |
| `main-updates` | main | only the bypass may update the branch | the role Repository admin, only through a pull request: only the owner's account merges into main. The Actions may push branches and open pull requests, but never merge |
| `tags` | `v*` | no deletion, no update, no force push; creating stays open for the release workflow | nobody: a version once out is never moved |

The repository's settings also delete head branches after a merge and offer only merge commits.
Squash and rebase merges are off, because the merge message carries the description, as the history shows
(`merge.py` takes it as `--subject "Merge branch 'cpl-turn': …"`).

- **Not strict.** A pull request need not sit on the newest main. Two branches merged within the same minutes must
  not both carry 0.2.6, since git merges two identical changes to one line without a conflict. `merge.py` prevents
  that: it merges only while main still has the number it numbered from (step 5 above). A strict rule would do the
  same at a high price. Every push of `TODO.md`, which comes many times an hour, would send each waiting pull request
  through its checks again. This was found while building TD-45, and it replaces the strict rule the owner confirmed.
- **Skipped counts as passed.** `paths` and `version` run only where they apply. GitHub counts a job
  skipped by its `if` as successful, so a required check never blocks a pull request it does not concern.
- **`main-updates`** closes the gap that [proposals-pipeline.md](../done/proposals-pipeline.md) found (its layer 1): today
  only the prompt keeps the Action from changing main. Whether GitHub accepts the admin role as a bypass on a personal
  repository is checked when the rules are applied. If it does not, this ruleset is left out and the working rule
  stays as it is.
- **In an emergency** the owner switches a ruleset off in the settings and on again afterwards. That is one click, and
  it shows in the ruleset's history.

### The check `paths`

The check holds each family of branches to its paths:

| Branch | May change | Must never change |
| --- | --- | --- |
| `notes/*` | `docs/concepts/**`, `TODO.md` | anything else |
| `rules/proposals`, `features/proposals` | the rest | `.github/`, `.claude/`, CLAUDE.md, `edakit/proposal.py`, `tests/test_proposal.py`, `skills/propose-rule/`, `skills/propose-feature/`, `pyproject.toml`, `uv.lock`: the pipeline is never changed through itself |
| any other | everything | – |

The version's own lines (`edakit/__init__.py`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `changes/`) lie
outside the proposals' list, so `merge.py` can number a proposals pull request too. The proposals' list comes from
[proposals-pipeline.md](../done/proposals-pipeline.md), section "The pipeline's paths". It lives once, in `edakit/proposal.py`
with a test. The lane's paths are `LANE` in `.github/versions.py`.

A branch must not be able to loosen its own check. A workflow on `pull_request` runs the head's version of its file,
so a branch that edits the check would pass it. So `paths` and `version` run on `pull_request_target`, from main's
workflow file and main's lists, and read nothing from the pull request but its changed files and, for `version`, the
number and the changelog's top section. They never check out or run the head's code. The jobs write their result as
a commit status named `paths` and `version` onto the pull request's head (`statuses: write`), so the required check
sits where GitHub and `merge.py` look for it, whatever commit a run on `pull_request_target` is reported on
(`.github/workflows/pull-request.yml`).

### What changes for a session

- **Nobody commits on main.** The main clone only follows main with `git pull --ff-only`. A push to main is refused
  with "Repository rule violations", and the commit moves to a branch.
- **Code** goes from a branch with its fragment to a pull request (`gh pr create`). With the owner's OK the session
  runs `.github/merge.py <n>`. The notice to the other sessions comes before the merge, as today.
- **A concept or a todo** goes through the notes lane.

## Concepts and the todo list: the notes lane

With a pull request required, every concept and every ticked todo would wait for the owner to merge it. The owner
would end up merging the tick of TD-12.

| Way | Why not |
| --- | --- |
| A bypass for the owner | every session has it, so the protection is gone for everything |
| Concepts on a branch | not "in the repository" for the owner (CLAUDE.md) |
| The wiki or Discussions | not in the repository, not on the site |
| An exception by path on main | GitHub's rules for a branch know none |
| An Action that merges notes itself | a merge by the GITHUB_TOKEN starts no workflow, so the site would not be published |

**The notes lane:**

- A pull request from `notes/<topic>` that changes only `docs/concepts/**` and `TODO.md` is merged by `notes.py` as
  soon as its checks are green. No OK is needed, as today. It needs no fragment and is no version.
- The required check `paths` (above) fails a `notes/` pull request that touches anything else, so no code reaches
  main through the lane, not even a change to the check itself.
- `notes.py` merges from the owner's account, so the push to main starts Pages, as today. GitHub's auto-merge is not
  used: it needs a setting, and before the rulesets it would merge before the checks ran (changed while building
  TD-46).
- A concept is on main about five minutes after the push, which is the time `test` takes, and on the site after that.

**One command**, `.github/notes.py "<message>" <files…>`, from any worktree on any branch:

1. It checks that every file named lies in the lane.
2. It takes the session's own edits of those files: the diff against the commit its checkout stands on, not the
   files themselves. A `TODO.md` taken whole from an older checkout would undo the ticks another session has landed in
   the meantime.
3. It applies those edits with a three-way merge onto the newest main, in a temporary index. The checkout, its branch
   and its other changes stay as they are. If two sessions changed the same lines, it stops and names them. The
   session pulls and runs it again.
4. It pushes the commit to `notes/<topic>`, opens the pull request, waits for the checks and merges it. If main has
   moved into a conflict in the meantime, it starts again from step 2 on the newest main. It ends with the merge or
   with a conflict it names. A session runs it in the background.
5. It puts the files in the checkout back to its commit, unless they were edited again in the meantime. They come back
   with main: the main clone on main is fast-forwarded by the script, and a code branch gets them with its next
   rebase. Git refuses to fast-forward over a working tree that holds the same edit uncommitted (tried on
   2026-11-01). The edits left in place would block the main clone's next pull.

Moving a concept from `new/` to `done/` changes links in the handbook or the README. That lies outside the lane and
becomes an ordinary pull request with the owner's OK, which fits, since moving a concept means it is settled. The lane
covers exactly these two paths and is widened only on the owner's word. `upstream/README.md`, for one, changes
together with code.

## Against the yardstick

Nothing is left only in EasyEDA or only in someone's head. Things that today exist only in one machine's plugin
cache become text:

- the version: `edakit/__init__.py`, the marketplace entry;
- the protection: `.github/rulesets/`;
- the history of what changed: `CHANGELOG.md` from `changes/`;
- which edakit released a board: its manifest;
- for a project that pins, which edakit it runs: its own settings and CI script.

## Steps

| Step | What | Files | Size | Waits for |
| --- | --- | --- | --- | --- |
| V.1 | The number in one place (0.2.0); `edakit --version`; the manifest's `tools.edakit` with the commit; the marketplace entry with version and ref; `plugin.json` without; the test that holds them together | `edakit/__init__.py`, `pyproject.toml`, `edakit/cli.py`, `edakit/release/gate.py`, `.claude-plugin/`, `tests/test_version.py` | S | – |
| V.2 | Changelog, fragments, merge: `CHANGELOG.md`, `changes/README.md` (the rule for the number), `.github/merge.py`, `.github/versions.py`, `release.yml`; the checks `paths` and `version` (on `pull_request_target`, their lists read from main); the working rule in CLAUDE.md – a fragment per branch, merging through `merge.py`; the reader's documentation: README (Install, Versions), handbook 2.3 (update, pin, `--version`), 10.5, 14.4, the glossary. On one branch with V.1: its merge is 0.2.0, the first version, tagged by `release.yml` | `CHANGELOG.md`, `changes/`, `.github/`, `edakit/proposal.py` (the list, with the proposals concept) | M | V.1 |
| V.3 | The notes lane: `.github/notes.py`, `paths` for `notes/*` | `.github/` | M | V.2 |
| V.4 | The rules as text, applied with `gh api` on the owner's word once V.2 and V.3 are on main (the required checks must exist), with the working rules that go with them: CLAUDE.md (the notes lane, the protection), `docs/organisation.md` (`changes/`, `CHANGELOG.md`, `.github/rulesets/`), the triage, add-rule and add-feature skills (a fragment per change) | `.github/rulesets/`, CLAUDE.md, `docs/organisation.md`, `.claude/skills/` | M | V.3 |
| V.5 | Branches left lying around: 9 `claude/*` and 2 `ccr-*` on origin, the local ones and worktrees – listed, then merged or deleted on the owner's word; other sessions' branches named with their session | – | S | – |
| V.6 | 1.0.0: on the owner's word, once D.2 of documentation.md is built (`merge.py --major`) | – | S | D.2 |
| V.7 | Later: `edakit = ">=0.4"` under `[project]` in `edakit.toml`. `edakit check` notes when the running edakit does not meet it, and the SessionStart hook says which edakit runs, so a project that needs a newer edakit says so | `edakit/config.py`, `edakit/agreements.py`, handbook 10 | M | V.2, the owner's word |

## Not proposed

- **A merge queue:** it would serialise the merges on GitHub's side, but GitHub offers it only to repositories owned
  by an organisation. `merge.py` does the same work for this repository.
- **Signed commits:** they would take a key in every session and in the Action, and protect against nothing that
  threatens this repository.
- **Conventional commits with release-please:** the commit messages here are prose that describes what changed, and
  the fragments carry the kind instead.
- **`claude plugin tag`:** its tags `edakit--v1.0.0` serve plugins that depend on edakit, and there are none.
- **A channel for main:** main holds nothing that is not already a version.

## Decisions

| # | Question | Recommended | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | The scheme and the first number | Semantic versioning from 1.0.0: three numbers, each with a meaning for a project | **0.2.0, and 1.0 once the documentation's entry layer is done**; CalVer (2026.11.0) – says when, not what to do | **0.2.0, 1.0 after D.2** (the owner, 2026-11-01). Added by the owner the same day: the major number is the owner's to release; minor and patch are Claude's; a new rule is a patch; the rest kept simple – minor when a project must act, patch otherwise |
| 2 | How concepts and TODO.md reach main | **the notes lane**, auto-merge once green | a pull request with the owner's OK, like code; a bypass for the owner, which is one for every session | **the notes lane** (the owner, 2026-11-01) |
| 3 | When a version is made | on the owner's word, several merges in one | **every merge into main a version of its own**; once a week | **every merge** (the owner, 2026-11-01): numbered by `merge.py` before the merge, which merges only while main still has the number it numbered from; a red `version` check before that |
| 4 | The owner's projects | each pins a version in its own repository, and a main channel for live runs | **the newest version, unpinned**; the main channel throughout | **the newest version, unpinned** (the owner, 2026-11-01): no main channel, pinning in the README for whoever wants it, pytree's D-50 its own |

What Claude decided itself, confirmed by the owner on 2026-11-01:

- no approval required;
- the checks strict (decision 3 makes it necessary) – replaced while building TD-45: not strict, `merge.py` holds the
  numbers apart ("Not strict" above);
- merge commits only;
- no bypass on `main`;
- the ruleset `main-updates`;
- tags never moved;
- head branches deleted after a merge;
- one question for minor or patch: a new command, key, maker or skill is a patch like a rule, since a project need
  not act;
- the changelog's first section collects the merges from 2026-11-01 on, from their merge messages;
- fragments, deleted by the merge;
- a merge that changes nothing a project reads, the notes lane among them, is no version – decided by its paths;
- the red check `version` until `merge.py` numbers the pull request, so the button cannot merge an unnumbered change;
- the number in `edakit/__init__.py`, `plugin.json` without a version, the marketplace entry at the tag;
- no channel for main;
- the lane only for `docs/concepts/` and `TODO.md`;
- no second identity for now.
