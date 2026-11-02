---
name: version
description: Show which edakit runs and which the plugin installed per scope (user, each project), the newest version on GitHub, what the changelog says in between – its "When updating:" lines first, what a project must do –, and where the project pins edakit (settings.json, CI, scripts), from `edakit version`; then update the plugin, pin the project at one version or let it follow the updates (`edakit version pin|unpin`), and write or renew the pre-commit hook (`edakit hook install`) – each on the owner's word. Use for "pin edakit", "unpin", "the hook is missing", "which edakit do I have", "is edakit up to date", "what is new in edakit", "update edakit", "/edakit:version".
---

# Which edakit, and what an update brings

Versions and pins: `${CLAUDE_PLUGIN_ROOT}/handbook/02-setup.md` (2.3), the command `edakit version` in
`10-reference.md`. Here only the procedure.
Where the session does not find `edakit` on the PATH, it is `${CLAUDE_PLUGIN_ROOT}/bin/edakit`.

## 1. Read

`edakit version 2>&1 | cat` in the project's repository – exit 0: nothing to act on, 2: findings (the lines `FINDING`
at the end), 1: an error. It reads only: the plugin's installations, the tags and the newest changelog from GitHub,
the project's pins. Without network the newest version stays unknown – say so, and leave it there.

## 2. Report

To the owner, short:

- **What runs here:** the edakit of the scope "in effect here", and whether it is the newest.
- **What an update means for the project:** each **When updating:** line of the versions in between, in the owner's
  words – what to change, which sign-offs to renew. None: "nothing beyond the update itself". The other lines of the
  changelog only when the owner asks, or as one line of what is new.
- **Pins:** where the project names a version or a commit (`.claude/settings.json`, CI, a script), and whether they
  agree with each other and with what runs. A pin is a choice of the project (handbook 2.3): name it, do not call it
  wrong.
- **Other scopes:** an installation of another project that is behind is one line, for that project's session.

The update, if one is due, goes into the reply's block for the owner – the command `edakit version` printed, with its
scope.

## 3. Update – on the owner's word

1. The command `edakit version` printed: `claude plugin marketplace update edakit && claude plugin update
   edakit@edakit`, with `--scope project` (or `local`) when that installation is the one in effect here.
2. The session runs the old edakit until `/reload-plugins` or a new session – that is the owner's to type. Say so.
3. After the reload, `edakit version 2>&1 | cat` once more: the scope in effect shows the newest.
4. **When updating:** steps are the project's own work – `edakit convert`, sign-offs renewed: each as its own step
   with the skill it belongs to (release for sign-offs), on the owner's word, not in this skill.

A project that pins edakit moves its pins itself: the tag in `.claude/settings.json` and in CI together, then the gate
and a commit (handbook 2.3) – on the owner's word, never as a side effect of the plugin update.

## 4. Pin or follow – on the owner's word

`edakit version pin [current|latest|X.Y.Z] 2>&1 | cat` lists what it would change: `[project] edakit = "==X"` in every
edakit.toml, every edakit call in CI and scripts at `@vX`, the marketplace's `ref` out of `.claude/settings.json`.
`edakit version unpin 2>&1 | cat` lists the way back: `>=X`, the calls without a ref. Show the list; on the owner's
word run it again with `--write`, then `edakit check 2>&1 | cat` and commit.

Say once what a pin holds and what it does not: the command line in CI and scripts runs exactly X; the plugin – skills,
agents, `edakit` in the session – cannot be held per project and keeps following its updates. Where it no longer meets
`==X`, the session start and `edakit check` say so (STRUCT.edakit); then either `pin latest` after reading the
changelog, or `unpin`.

## 5. The pre-commit hook

When the session start names the hook – missing, no edakit block, an older one, not run by git –, `edakit hook check
2>&1 | cat` shows what, and `edakit hook install 2>&1 | cat` on the owner's word writes or renews edakit's block and
activates it. Lines it names as running edakit outside the block are the project's to take out – a wrapper script of
its own among them; show them, change them on the owner's word, and commit the hook.
