patch
- The explorative DSL, a beta: a project that sets `[beta] dsl = true` in edakit.toml may write its graph as
  `hardware/graph.circuit` in the circuit language – definitions, usages, loops, parameters, aliases, includes,
  derivation rules and variants –, its requirements as `hardware/requirements.circuit`, and use `edakit graph
  fmt|derive|sysml|kerml`, `graph convert --to circuit`, `graph json --map`, `block add --set/--part` and `edakit lsp`
  with the VS Code extension of `editors/vscode/`. Without the switch nothing changes: such a file, a list of parts
  folders and those commands are refused with one line that names the switch. The site has a tab "Explorative DSL"
  (docs/dsl/); the codes of the DSL – DEF.derive, SYNC.graph – are not in the catalog, `edakit explain` names them.
- `edakit graph fmt --check FILE …` takes its files after the option on Python 3.11 and 3.12 as well.
