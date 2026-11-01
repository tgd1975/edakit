# Versions and branch protection: what a version of edakit is, how main is protected, how a concept still gets there

Status 2026-11-01: proposed – four decisions open and the ones Claude took itself to confirm (the table at the end);
nothing built. Written against main at `d633a4b`. Asked for by the owner: edakit has reached the point where it should
work with version numbers and branch protection from now on – a concept for both, and, since a concept could then no
longer be committed straight to main, an elegant way for concepts to get there all the same.

## The short answer

A version of edakit gets three numbers, and each one tells a project something: the first one means "change your files
or sign again", the second "you may get new findings", the third "nothing to do". The number is written in one place.
The marketplace entry points at the version's tag, so a project installs the newest version, not whatever main holds
that minute. A project can also pin a version in its own repository. The changelog is assembled from one small file
per branch, so parallel sessions never conflict over it, and the kinds of those files give the next number. A version
is made on the owner's word: one pull request, and its merge tags it.

main gets rulesets that are kept as JSON in the repository. Every change comes through a pull request with green
checks. Nobody may force-push or delete main, and the owner has no bypass. One fact shapes all of it: every session
acts as the owner's GitHub account. GitHub cannot tell a session from the owner, so the protection guards against
slips and against the Actions. It does not lock out the sessions, and the owner's OK for code stays a working rule.

Concepts and the todo list keep their speed through the **notes lane**. A pull request from a branch `notes/<topic>`
that changes only `docs/concepts/` and `TODO.md` merges itself once its checks are green, with no OK needed, as today.
A required check makes sure nothing else slips through that lane. One command lands a session's edits there from any
worktree and any branch, with the checkout left alone. The concept is on main about five minutes later.

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

### The three numbers

Semantic versioning, read for a hardware project. Three questions are asked of every change, in this order:

| Number | Question | Examples |
| --- | --- | --- |
| **Major** | Must a project change one of its files, or sign again, to stay green? | a key, file format, command or exit code removed or changed in meaning; a hash computed differently (sign-offs void); a retired code that waivers name; a new seal format |
| **Minor** | Can an unchanged, green project get a new finding, or something new to use? | a new check, code, hint, block, parts entry, maker, key or command; a severity raised; a check that now finds what it missed |
| **Patch** | Neither | a false finding gone, a crash fixed, the handbook, a prompt's wording |

A major version brings a way across with it: `edakit convert` where a format changes, and in every case a section
"When updating" in the changelog that lists each step a project takes, such as which sign-offs to renew. The
implementation plan already names every hash a step changes. Under this scheme every such step is a major version.

### Where the number is written

- **One place.** The text `__version__ = "1.0.0"` in `edakit/__init__.py`. `pyproject.toml` reads it from there
  (hatch: `dynamic = ["version"]`, `[tool.hatch.version] path`), so even a checkout that nothing has installed can be
  read.
- **The marketplace entry** carries `version` and the source `{"source": "github", "repo": "tgd1975/edakit",
  "ref": "v1.0.0"}`. `plugin.json` stays without a version, because Claude Code would take that one first, and it
  would freeze the main channel (below).
- **A test holds them together:** the entry's version equals the package's, the ref is `v` plus that number, and the
  top section of the changelog has that number.
- **`edakit --version`** prints `1.0.0`. From a git checkout away from the tag it prints `1.0.0+g1a2b3c4`. The gate
  manifest's `tools.edakit` takes the same string, so a manifest names the edakit that released the board, down to
  the commit if it was not a version.

### How a project gets a version

Claude Code has no release channels of its own. Its documented way is one marketplace file per channel, each with an
entry at its own ref (code.claude.com, plugins: "Host and maintain", "Release channels"). It keys its cache by
version. A plugin is only updated when the version changes, and a running session keeps the old one until
`/reload-plugins` or a new session starts.

| Channel | How | For |
| --- | --- | --- |
| **The newest version** | `/plugin marketplace add tgd1975/edakit`, as today. The marketplace comes from main, its entry points at the newest tag. Updating is the same command as today (README, Install). Auto-update is off for marketplaces outside Anthropic | everyone, the default |
| **Pinned** | in the project's `.claude/settings.json` `"ref": "v1.2.0"` in the github source of `extraKnownMarketplaces.edakit`. The command line in its CI: `uvx --from git+https://github.com/tgd1975/edakit@v1.2.0 edakit` | a project that releases boards: skills and command line of the same version, written in its own repository |
| **main** | a second marketplace `edakit-main`, `.claude-plugin/main/marketplace.json`, whose entry points at `"ref": "main"` and has no version. Claude Code then takes the commit, as today. In settings: `"path": ".claude-plugin/main/marketplace.json"` | the owner's projects during a live run of something not yet in a version; nobody else |

A pinned project moves up when its own session decides to. It reads the changelog's "When updating", changes the ref,
runs the gate and commits.

### The changelog

`CHANGELOG.md` sits at the root, newest version first. Each section has the date, and under it "When updating" (major
only), "New findings", "New" and "Fixed". It is written for a maker who updates, not for whoever wrote the code.

Its lines come from **fragments**. Each branch writes one file of its own, `changes/<branch>.md`. The first line
gives the kind (`breaking`, `check`, `feature`, `fix` or `none`), and the lines after it are the text for the
changelog. A single "Unreleased" section would conflict on almost every merge while several sessions merge in
parallel, but a file per branch never conflicts. The kinds also give the next number, so nobody picks it by hand: any
`breaking` makes a major version, any `check` or `feature` a minor one, and anything else a patch. `none` says on
purpose that a change has nothing for the changelog, such as a test or CI.

A required check `changes` fails a pull request that changes code, data, skills, agents, hooks or the handbook but
carries no fragment. The notes lane and the version's own pull request are exempt. Every proposal that triage
accepts adds its own fragment (`changes/rule-<issue>.md`, `changes/feature-<issue>.md`), which is one line more in
the triage skills.

### Making a version

edakit's own word "release" already means a board's release (handbook 8, `edakit release`). So this concept speaks of
"a version of edakit" and of "edakit's GitHub release", and the handbook keeps "release" for the board.

On the owner's word, a session runs `uv run python .github/release.py`. The script:

- reads the fragments and works out the next number from their kinds;
- writes the changelog's new section and deletes the fragments;
- sets the number in `edakit/__init__.py` and in the marketplace entry;
- commits on `release/v1.3.0` and opens the pull request "edakit 1.3.0", whose text is the changelog section.

The owner merges it. The workflow `release.yml` runs on every push to main. When the package's version has no tag yet,
it sets the tag `v1.3.0` on that commit and opens the GitHub release with the section as its text. From that moment
the marketplace entry's ref exists. A fragment that is merged while the release pull request waits is simply part of
the next version, and nothing conflicts.

A project that waits for a fix gets it the same way, within minutes. There are no hotfix branches, because main can
always be released: every merge was green.

## Branch protection

### The fact that shapes it

Every session pushes and merges as the owner's account. Any right the owner keeps, every session has too, and any
bypass the owner gives himself is a bypass for all of them. So the rules below guard against three things:

- a slip, such as a commit on local main or a push of a red branch;
- a force push;
- the Actions: the proposals pipeline runs Claude with the Claude App and the GITHUB_TOKEN, both with `contents:
  write`.

The owner's OK for code stays a working rule in CLAUDE.md. A real lock would take a second identity for the sessions,
a GitHub App or a machine account, plus a required approval from the owner on every pull request. That is not proposed
now: it costs an identity handed to every session and a click on GitHub for each merge, against a risk the working
rule has handled so far. The option stays open.

### The rules, as text

The files sit in `.github/rulesets/` and are applied with `gh api`. The protection is then text in the repository like
everything else. A change to it goes through a pull request and is applied after the merge, on the owner's word.

| Ruleset | Target | Rules | Bypass |
| --- | --- | --- | --- |
| `main` | main | a pull request, no approval required (the owner cannot approve his own, and the sessions are the owner); the checks `test`, `kicad`, `build`, `paths` and `changes` green, not strict; no force push; no deletion | nobody, the owner included |
| `main-updates` | main | only the bypass may update the branch | the role Repository admin, only through a pull request: only the owner's account merges into main. The Actions may push branches and open pull requests, but never merge |
| `tags` | `v*` | no deletion, no update, no force push; creating stays open for the release workflow | nobody: a version once out is never moved |

The repository's settings also allow auto-merge, delete head branches after a merge, and offer only merge commits.
Squash and rebase merges are off, because the merge message carries the description, as the history shows:
`gh pr merge <n> --merge --subject "Merge branch 'cpl-turn': …"`.

- **Not strict.** A pull request does not need to sit on the newest main. With five sessions merging, a strict rule
  would send every open pull request into a new run after each merge, and auto-merge would wait for a click on
  "Update branch". The working rule "rebased" stays for code branches. The run on main after every merge is the safety
  net, and a red main is fixed first.
- **Skipped counts as passed.** `paths` and `changes` run only where they apply. GitHub counts a job skipped by its
  `if` as successful, so a required check never blocks a pull request it does not concern.
- **`main-updates`** closes the gap that [proposals-pipeline.md](proposals-pipeline.md) found (its layer 1): today
  only the prompt keeps the Action from changing main. Whether GitHub accepts the admin role as a bypass on a personal
  repository, and whether a merge by auto-merge counts as the account that switched it on, is checked when the rules
  are applied. If either fails, this ruleset is left out and the working rule stays as it is.
- **In an emergency** the owner switches a ruleset off in the settings and on again afterwards. That is one click, and
  it shows in the ruleset's history.

### The check `paths`

The check holds each family of branches to its paths:

| Branch | May change | Must never change |
| --- | --- | --- |
| `notes/*` | `docs/concepts/**`, `TODO.md` | anything else |
| `release/v*` | `CHANGELOG.md`, `changes/`, `edakit/__init__.py`, `.claude-plugin/marketplace.json` | anything else |
| `rules/proposals`, `features/proposals` | the rest | `.github/`, `.claude/`, CLAUDE.md, `edakit/proposal.py`, `tests/test_proposal.py`, `skills/propose-rule/`, `skills/propose-feature/`, `pyproject.toml`, `uv.lock`: the pipeline is never changed through itself |
| any other | everything | – |

The proposals' list comes from [proposals-pipeline.md](proposals-pipeline.md), section "The pipeline's paths". It
lives once, in `edakit/proposal.py` with a test. The lane's paths live in `.github/notes.py`.

A branch must not be able to loosen its own check. A workflow on `pull_request` runs the head's version of its file,
so a branch that edits the check would pass it. So `paths` runs on `pull_request_target`, from main's workflow file
and main's lists, and reads nothing but the list of changed files from the pull request. It never checks out or runs
the head's code. When the rules are applied, a test confirms that GitHub counts this run as the required check on the
pull request's head. If not, the job writes the status `paths` onto the head commit itself (`statuses: write`).

### What changes for a session

- **Nobody commits on main.** The main clone only follows main with `git pull --ff-only`. A push to main is refused
  with "Repository rule violations", and the commit moves to a branch.
- **Code** goes from a branch to a pull request (`gh pr create`). With the owner's OK the session runs
  `gh pr merge <n> --merge`, or adds `--auto` while the checks still run. The notice to the other sessions comes before
  the merge, as today.
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

- A pull request from `notes/<topic>` that changes only `docs/concepts/**` and `TODO.md` merges itself once its checks
  are green. The session switches on auto-merge, and no OK is needed, as today.
- The required check `paths` (above) fails a `notes/` pull request that touches anything else, so no code reaches
  main through the lane, not even a change to the check itself.
- Auto-merge runs as the account that switched it on, which is the owner's. So the push to main starts Pages, as
  today.
- A concept is on main about five minutes after the push, which is the time `test` takes, and on the site after that.

**One command**, `.github/notes.py "<message>" <files…>`, from any worktree on any branch:

1. It checks that every file named lies in the lane.
2. It takes the session's own edits of those files: the diff against the commit its checkout stands on, not the
   files themselves. A `TODO.md` taken whole from an older checkout would undo the ticks another session has landed in
   the meantime.
3. It applies those edits with a three-way merge onto the newest main, in a temporary index. The checkout, its branch
   and its other changes stay as they are. If two sessions changed the same lines, it stops and names them. The
   session pulls and runs it again.
4. It pushes the commit to `notes/<topic>`, opens the pull request and switches on auto-merge. With `--wait` it
   stays until the pull request is merged, or until it can no longer be merged.
5. It puts the files in the checkout back to its commit. They come back with main: the main clone gets them with
   `git pull --ff-only`, a code branch with its next rebase. Git refuses to fast-forward over a working tree that holds
   the same edit uncommitted (tried on 2026-11-01). The edits left in place would block the main clone's next pull.

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
- which edakit a project runs: its own settings and CI script;
- which edakit released a board: its manifest.

## Steps

| Step | What | Files | Size | Waits for |
| --- | --- | --- | --- | --- |
| V.1 | The number in one place; `edakit --version`; the manifest's `tools.edakit` with the commit; the marketplace entry with version and ref; `plugin.json` without; the test that holds them together | `edakit/__init__.py`, `pyproject.toml`, `edakit/cli.py`, `edakit/release/gate.py`, `.claude-plugin/`, `tests/test_version.py` | S | decision 1 |
| V.2 | Changelog and fragments: `CHANGELOG.md` opened with the first version, `changes/README.md` (the kinds), `.github/release.py`, `release.yml`; the checks `paths` (on `pull_request_target`, its lists read from main) and `changes` | `CHANGELOG.md`, `changes/`, `.github/`, `edakit/proposal.py` (the list, with the proposals concept) | M | V.1, decision 3 |
| V.3 | The notes lane: `.github/notes.py`, `paths` for `notes/*` | `.github/` | M | V.2, decision 2 |
| V.4 | The main channel | `.claude-plugin/main/marketplace.json` | S | V.1, decision 4 |
| V.5 | The rules as text, applied with `gh api` on the owner's word once V.2 and V.3 are on main (the required checks must exist), with the working rules that go with them: CLAUDE.md (Concepts and branches), `docs/organisation.md` (`changes/`, `CHANGELOG.md`, `.github/rulesets/`), the triage, add-rule and add-feature skills (a fragment per change), README (Install) and handbook 2.3 (pin, update) | `.github/rulesets/`, CLAUDE.md, `docs/organisation.md`, `.claude/skills/`, README.md, handbook 2 | M | V.3 |
| V.6 | The first version: `release.py`, tag, GitHub release | – | S | V.5 |
| V.7 | Branches left lying around: 9 `claude/*` and 2 `ccr-*` on origin, the local ones and worktrees – listed, then merged or deleted on the owner's word; other sessions' branches named with their session | – | S | – |
| V.8 | The bell and pytree pin the first version: the ref in their settings, `EDAKIT_REV` in pytree's `hardware/edakit.sh`. Done in their repositories by their sessions, at the owner's request | the projects | S each | V.6, decision 4 |
| V.9 | Later: `edakit = ">=1.2"` under `[project]` in `edakit.toml`. `edakit check` notes when the running edakit does not meet it, and the SessionStart hook says which edakit runs, so a plugin and a command line pinned apart no longer drift unnoticed | `edakit/config.py`, `edakit/agreements.py`, handbook 10 | M | V.6, the owner's word |

## Not proposed

- **A merge queue:** GitHub offers it only to repositories owned by an organisation.
- **Signed commits:** they would take a key in every session and in the Action, and protect against nothing that
  threatens this repository.
- **Conventional commits with release-please:** the commit messages here are prose that describes what changed, and
  the fragments carry the kind instead.
- **`claude plugin tag`:** its tags `edakit--v1.0.0` serve plugins that depend on edakit, and there are none.

## Decisions

| # | Question | Recommended | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | The scheme and the first number | Semantic versioning from **1.0.0**: three numbers, each with a meaning for a project | 0.2.0, and 1.0 once the documentation's entry layer is done – but 0.x folds "sign again" and "new findings" into one number; CalVer (2026.11.0) – says when, not what to do | open |
| 2 | How concepts and TODO.md reach main | **the notes lane**, auto-merge once green | a pull request with the owner's OK, like code; a bypass for the owner, which is one for every session | open |
| 3 | When a version is made | **on the owner's word**, several merges in one | every merge into main a version of its own; once a week | open |
| 4 | The owner's projects | **each pins a version** in its own repository (V.8), and the main channel only for live runs | the newest version unpinned; the main channel throughout | open |

What Claude decided itself, to be confirmed with them: no approval required; the checks not strict; merge commits
only; no bypass on `main`; the ruleset `main-updates`; tags never moved; head branches deleted after a merge;
fragments instead of an "Unreleased" section; the number in `edakit/__init__.py`; `plugin.json` without a version; the
main channel as a second marketplace; the lane only for `docs/concepts/` and `TODO.md`; no second identity for now; a
version made as a pull request whose merge sets the tag.
