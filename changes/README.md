# Fragments

One file per branch, `changes/<branch>.md`, says what the branch changes for a project – the line the changelog gets
when `.github/merge.py` merges it as a version of its own. On main this folder holds nothing but this page: the merge
turns the fragments into the version's section of [CHANGELOG.md](../CHANGELOG.md) and deletes them.

```markdown
patch
- GEO.pour finds every bare area above `[copper] max_bare_mm2` on each side, not only the largest circle (#103).
```

The first line is the number that goes up – one question settles it:

| Does a project have to do something when it updates? | First line | Examples |
| --- | --- | --- |
| yes – change one of its files, or sign again | `minor` | a key, file format, command or exit code removed or changed in meaning; a hash computed differently, so sign-offs are void; a retired code that waivers name |
| no | `patch` | a new rule (check, hint, block, parts fact), a severity raised, a new command, key, maker or skill, a fix, the handbook, a prompt |

A `minor` fragment's lines begin with **When updating:** and say what a project does – `edakit convert`, which
sign-offs to renew. The major number is the owner's: `merge.py <n> --major`, only on the owner's word.

A branch that changes nothing a project reads – only `tests/`, `.github/`, `evals/`, `docs/`, `examples/`,
`upstream/`, `.claude/`, `TODO.md`, `CLAUDE.md`, `README.md` – needs no fragment and is merged without a version. The
check `version` of a pull request says which case it is (`.github/versions.py`).

Dependabot (`.github/dependabot.yml`) writes no fragment: for its branches `dependabot/…` that change `uv.lock` or
`pyproject.toml`, `merge.py` writes it – `patch`, with the pull request's title. A new major of a dependency is not
proposed; it comes by hand, with a fragment of its own. An update that moves only the dev tools – the group `dev` in `pyproject.toml`,
what it pulls into `uv.lock` – is no version: nothing edakit installs has changed.
