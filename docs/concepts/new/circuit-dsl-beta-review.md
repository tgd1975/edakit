# The beta's seal: what the review of the DSL branch found, and what closes it

Status 2026-11-03: concept, from the review of the branch `claude/friendly-mccarthy-n4kt6y` at `5ee220f` against
main at `46ad6af`, asked for by the owner the same day. The yardstick was the owner's word of decision 48 of
[circuit-dsl-toolchain.md](circuit-dsl-toolchain.md): the original form is the default without a word about the DSL,
every facet of the DSL works only in a project whose edakit.toml switches it on, the site has a top-level section
"Explorative DSL". Built the same day on the owner's word ("setze das … dokument um"): B.1 to B.6 on the branch
`explorative-dsl-beta-fixes`, five commits on the DSL branch's tip `5ee220f` (`1dd3e31` to `460a3e4`) – the DSL
branch itself is another session's and unchanged; it takes them as a fast-forward. The decisions below taken as
recommended and confirmed by the owner the same day (decision 50 of circuit-dsl-toolchain.md). Left: the
fast-forward of the DSL branch, the session that holds it; the branch is not proposed for main until the owner
asks (decision 48).

## Why

Decision 49 describes the beta as built: `[beta] dsl = true` in edakit.toml switches the DSL on (`edakit/beta.py`),
without it the DSL's files, commands and keys are refused with one line, the help hides its actions, the catalog, the
handbook and `edakit rules` leave its codes out, the DSL's text is `docs/dsl/`. The review checked that against the
code, the tests, the site and a project without the switch – the same led-bar on main and on the branch, every
everyday command, byte for byte. Most of it holds; five things do not, and a sixth is a crash. They are small, each
one a line or two, but together they are the difference between "a project without the switch is main" and "almost".

## What the review found

The checks the branch passes, for the record: `pytest -q -n auto` – 3532 passed on the branch, 3092 on main, the same
34 environment failures on both (no ngspice in the container, a font metric in `schematic draw`) and the same 34 with
main merged in; the bell's golden tests with `BELL_ROOT`, 19 passed; `python -m edakit.catalog.handbook --write`,
`python -m edakit.lang.blocks --write` and `docs/catalog/build.py` change nothing, on the branch and with main merged;
`docs/pages.py` and `mkdocs build --strict` green, the tab "Explorative DSL" between Reference and Inside edakit, the
beta notice on all six pages, no dead link; `ruff check` green; the VS Code extension compiles; the pull request's
checks `version` and `paths` pass with the fragment `changes/claude-friendly-mccarthy-n4kt6y.md` (`patch`, right by
`changes/README.md`: no project must act); `git merge-tree` against today's main has no conflict, nothing of main is
lost or overwritten. With the switch, `convert --to circuit`, `check`, `graph json --check` and `--write`, `fmt`,
`derive`, `sysml`, `kerml`, `block add --set`, the requirements notation, the language server's functions and a
variant with `of ../` all work on led-bar. `block list` and `block show` are byte-equal to main although the block
JSON now carries `params` and `derivations`. No command writes before it refuses: `HOOKED` of `edakit/scripts.py`
has no graph or block action, and the refusal sits before `check` and `block` in `edakit/cli.py`.

The findings, the heaviest first. "Reproduced" means a command was run and the output seen.

1. **The DEF engine runs without the switch.** `edakit/engines/__init__.py:74` puts `derive` into the list of
   graph engines unconditionally. A JSON project without `[beta]` whose graph carries a key `derivations` – written by
   hand, since `block add --set` is refused – gets `DEF.derive – derived values within their window: 1 warning` from
   `edakit check`, with a fix text that names `edakit block add --set` and `.circuit`; main reports nothing for the same
   graph. `docs/dsl/README.md:27` says "no DEF" without the switch. Reproduced.
2. **argparse's error messages name the DSL.** `edakit/cli.py:124` keeps `fmt`, `derive`, `sysml` and `kerml` in
   `choices` of `graph`'s action, `:138` registers `lsp` as a subcommand, `:132` gives `--to` the choice `circuit`;
   the metavar hides them in `--help` only. `edakit graph bogus` answers "invalid choice: 'bogus' (choose from 'show',
   'json', 'convert', 'fmt', 'derive', 'sysml', 'kerml')", `edakit bogus` lists `lsp` and prints the whole metavar
   where main prints "argument command", `edakit graph convert --to x` names `circuit`.
   `tests/test_beta.py:84` holds `format_help()` only, not the error texts. Reproduced.
3. **`edakit graph` swallows surplus positional arguments.** `edakit/cli.py:384-390` parses with
   `parse_known_args` and appends every leftover without a dash to `args.files`, for the sake of `graph fmt --check A
   B` on Python 3.11 and 3.12. `edakit graph show U1 extra` is exit 2 "unrecognized arguments: extra" on main and exit
   0 on the branch, showing U1 – a change for every project, switch or not. Reproduced.
4. **Two messages name `.circuit` without the switch.** `edakit/graph_form.py:151` and `:181`: a JSON project
   without `[beta]` running `edakit graph json --check` reads "… checks the file beside a TOML or a .circuit graph".
   The only difference in the everyday commands' output between main and the branch. Reproduced.
5. **The beta notice names the branch.** `docs/dsl/README.md:4`: "it lives on the branch
   `claude/friendly-mccarthy-n4kt6y`". The site publishes the sentence; after a merge it is false, and a reader of the
   site is not helped by a branch name either way.
6. **`beta.dsl_of` crashes on an edakit.toml that is not UTF-8.** `edakit/beta.py:28` catches `TOMLDecodeError`
   and `AttributeError`, not `UnicodeDecodeError`: a file with a byte 0xFF makes `edakit graph fmt FILE` and every
   request of the language server raise instead of answering the refusal line. Reproduced. Otherwise the function is
   robust: a broken TOML, `dsl = "true"`, `dsl = 1`, `beta = 1`, a missing file, a path without edakit.toml all give
   False; a nested project takes the nearest edakit.toml upward; a symlink is resolved and its target's project decides.
7. **Three readers of the switch, two forms they disagree on.** `edakit/config.py:945` and `edakit/beta.py:19` read
   with tomllib, `edakit/agreements.py:187-190` with a regular expression, like the hook's other keys. For
   `beta = { dsl = true }` or `beta.dsl = true` the config and `dsl_of` say on, the session start says nothing.
   Reproduced; the same pattern as `kicad()` there, so a note rather than a defect.
8. **One link from the rest of the site into the tab.** `evals/README.md:63` describes the three DSL evals under
   "Inside edakit" and links `docs/dsl/`; nothing else outside the navigation points there, the concept pages link the
   concept, which is main's. The site's search indexes the DSL's pages like any other. Seen in the built site.
9. **Small things, not reproduced.** The docstring of `edakit/engines/project.py:5` says SYNC.graph runs "beside a
   TOML or a .circuit graph", the code runs it with `cfg.dsl` only; `edakit/catalog/handbook.py:136` filters the
   commands by a substring of the metavar; `config.DSL_DOC` repeats `beta.DOC`.

Two things the review met are decided, not findings: `edakit graph fmt` on a source of edakit's own block library
works from any project (`edakit/beta.py:15,22`; decision 49, "edakit's block sources always pass"), and
`edakit explain DEF.derive` answers by name (decision 49, "`edakit explain` naming them").

## What to do

On the branch, one commit per step, add-feature's order – the test first, then the code, the handbook's and the DSL's
pages where they say what changes. Every step keeps `tests/test_beta.py` as the place that holds the side without the
switch. Sizes as in the plans: S a day or less.

- **B.1 The DEF engine behind the switch (finding 1), S.** `graph_findings(ctx)` in `edakit/engines/__init__.py`
  takes `derive` only when the context's config has `dsl` – the context carries the config already for the profile;
  where it has none (`Design.from_data` in tests), the engine is off. A test in `tests/test_beta.py`: a JSON graph with
  a `derivations` record outside its window gives no finding without the switch and the DEF.derive warning with it.
  `docs/dsl/README.md` keeps "no DEF" and is then right.
- **B.2 The parser without the DSL's words (finding 2), S.** The DSL's actions, `lsp` and `--to circuit` leave the
  parser's `choices`: `graph`'s action is checked in `_main` – `show`, `json`, `convert` for every project, the four
  of `DSL_ACTIONS` only with the switch, else the one refusal line that names the switch, as `graph fmt` answers today;
  `lsp` is a subcommand the parser does not know, `_main` takes `argv[0] == "lsp"` before parsing; `--to` is a plain
  string checked in `main_convert`. An unknown action or `--to` then errors as on main, word for word. The handbook's
  generated `command` sections stay as they are (`handbook.commands()` reads the subparsers; `lsp` is no longer there
  to filter). The test holds the error texts: `edakit graph bogus`, `edakit bogus`, `edakit graph convert --to x`
  against main's wording, through `cli.main` and `capsys`.
- **B.3 No surplus arguments on `graph` (finding 3), S.** `parse_known_args` goes; `graph fmt`'s files become a
  positional `files` with `nargs="*"` declared after `name` – argparse on 3.11 and 3.12 fills them in order when
  `--check` comes first, which the fragment's second line then no longer has to promise – or, where that breaks
  `graph show NAME`, `fmt` parses its own files from `argv` in `_main` before the parser sees them. `edakit graph show
  U1 extra` is exit 2 again; a test holds it, and `tests/test_lang_fmt.py` keeps `fmt --check A B`.
- **B.4 The messages of a JSON project (finding 4), S.** The two sentences in `edakit/graph_form.py` name "a TOML
  graph" as on main; the `.circuit` half of each goes into a sentence that is printed only when the project has the
  switch, or is dropped – `docs/dsl/README.md` says it already. The test runs `graph json --check` and `--write` on a
  JSON project without the switch and compares with main's wording.
- **B.5 The crash and the notice (findings 5 and 6), S.** `dsl_of` catches `UnicodeDecodeError` and `OSError` with
  the rest and answers False; a test with a file of invalid bytes. The beta notice of `docs/dsl/README.md` – and the
  one every page of `docs/dsl/` repeats – names no branch: "not part of the released edakit, switched on per project,
  its form may change" is enough; a reader who wants the branch finds it in decision 48.
- **B.6 The notes (findings 7 to 9), S, optional.** `agreements.dsl()` may stay a regular expression, as the hook's
  other keys are; the two spellings it misses are worth one line in `docs/dsl/README.md` ("as a table `[beta]`") or
  nothing. The sentence on the DSL's evals in `evals/README.md` keeps its link – a source names what it covers – or
  loses it, the owner's call. The docstring of `engines/project.py` says "with the switch"; `DSL_DOC` reads from
  `beta.DOC`.

After B.1 to B.5 the review's sentence turns: a project without the switch is main – the same output for every
command, error texts included –, and with the switch everything the branch built works. The branch stays a branch
until the owner asks for its pull request (decision 48); the steps are its own commits, no fragment line changes
(`patch` stays).

## Decisions

Taken on 2026-11-03 as recommended, while building, and confirmed by the owner the same day:

1. **DEF without the switch (B.1):** off without the switch – it is what decision 49 and `docs/dsl/README.md` say;
   the alternative was on for every project, since a `derivations` key reaches a JSON graph only by hand.
2. **The link from the evals' README (B.6):** kept – the evals are a source behind "Inside edakit", and their page
   says what it covers; the alternative was to cut it so that only the tab leads into the DSL.
3. **The branch name in the beta notice (B.5):** dropped; the notice says how a project switches the DSL on.

## As built

On `explorative-dsl-beta-fixes`, each step test first, `tests/test_beta.py` holding the side without the switch:

- **B.1** (`1dd3e31`): `graph_findings` in `edakit/engines/__init__.py` runs DEF only where the project's config has
  `dsl`; without a project it does not run.
- **B.2, B.3** (`5289e66`): `build_parser(dsl=False)` in `edakit/cli.py` is main's parser word for word – no DSL
  action, no `lsp`, no `--to`, `--out`, `--map`, `--set`, `--part`. `dsl_words(argv)` opens the DSL's parser only for
  a command line that names one of them – `lsp`, a DSL action after `graph`, after `graph` or `block` `--to circuit`,
  `--to toml` or another of the options; the other commands' own `--out` stays theirs. `dsl_used(args)` names the
  command a project without the switch refuses. Only `graph fmt` takes files beyond its positionals (the 3.11 and
  3.12 case of the fragment); `graph show U1 extra` is exit 2 again. `handbook.commands()` lists the parser's commands
  as on main. One way it differs from the plan of B.2: the DSL's parser keeps `--to` as a choice of `toml` and
  `circuit` instead of a string checked in `main_convert` – `graph convert --to x` never reaches it, since
  `dsl_words` opens it for those two values or another word of the DSL only.
- **B.4** (`e978861`): `graph_form.sources(cfg)` – the two messages of `graph json` name "a TOML graph" as on main,
  "or a .circuit graph" with the switch.
- **B.5** (`649de4e`): the notice of the six pages of `docs/dsl/` names the switch, not a branch, and a test holds
  it; `beta.dsl_of` answers False for an edakit.toml that cannot be read or is no UTF-8.
- **B.6** (`460a3e4`): the session start reads `[beta] dsl` with tomllib where there is one – a table, `beta.dsl =
  true`, an inline table, as edakit.toml's check and `dsl_of` read them –, the regular expression only without it;
  `config.py` takes the DSL's page from `beta.DOC`; the docstring of `engines/project.py` says "with the switch".

Checked on the branch: `pytest -q -n auto` 3545 passed, the same 34 environment failures as main (no ngspice, a font
metric); the bell's golden tests with `BELL_ROOT` 19 passed; handbook, block JSON and catalog generated without a
diff; `mkdocs build --strict` green; `ruff check` green. led-bar without the switch, against the main the branch last
merged (`fe47cd3`): `version`, `check`, `graph json --check` and `--write`, `req`, `domains`, `gate`, `hook check`,
`rules`, `explain LIM.v`, `graph show`, `block add --dry-run` and `part lint` byte for byte the same, and the errors
of `edakit bogus`, `graph bogus`, `graph convert --to x` and `graph show U1 extra` too; what differs is what decision
49 decides – the refusal line of a DSL command, `edakit lsp` and `explain` of the DSL's codes by name. With the switch
`convert --to circuit`, `check`, `fmt --check A B`, `sysml`, `block add --set` and `graph json --check` work.

## Sources

- [circuit-dsl-toolchain.md](circuit-dsl-toolchain.md), decisions 48 and 49: the beta as decided and as built.
- `CLAUDE.md`, `docs/organisation.md`, `docs/concepts/done/versioning.md` and `changes/README.md`: the rules the
  review read the branch against.
- The review session of 2026-11-03 on the branch at `5ee220f` and main at `46ad6af`: the commands above, each run on
  copies of `tests/fixtures/led-bar` with and without the switch, on main and on the branch, and the bell's clone for
  `tests/test_lang_golden.py`.
