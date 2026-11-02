patch
- The parts library has a slide switch, SS-12D00-G3 (C22355741), and a 9 V battery snap with leads (C70374), both
  drafts from their datasheets; handbook 4.1 says how `edakit part add` lists the library by kind and how an entry the
  library lacks is written.
- `edakit hook install` names a step the session may not do – the hook's write, `git config core.hooksPath` – as a
  line `failed: …` with the command to run by hand, and exits 1; before, a refused `git config` was reported as done.
  The skill new-project goes on without them and puts them in its report.
- Every skill that runs `edakit` names `${CLAUDE_PLUGIN_ROOT}/bin/edakit` for a session that does not find it on the
  PATH – before the project has an edakit.toml, the session start does not.
- The handbook: the smallest edakit.toml for a circuit without a board of its own (2.7, 10.1); a switch closed unless
  the load lists it in `open`, a 9 V block as one cell state (5.1, 5.2); the form of the rows a requirement's `verify`
  names, SIM.state's among them (10.4). The newcomer's eval of documentation-newcomer.md found these missing.
