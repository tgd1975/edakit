patch
- The circuit language, step T.1 of circuit-dsl-toolchain.md: quantities with units, ranges and tolerances
  (`edakit/lang/units.py`) and the E-series E6 to E96 of IEC 60063 as a catalog table (`tables/series.toml`).
- T.2: the reader of the circuit language – `edakit/lang/tokens.py`, `model.py`, `reader.py` and the attribute
  table `schema.py`: every statement of language 5 with its file and line, every error at once.
- T.3: the attribute table held to handbook 3.1 by a test; an unknown key names the nearest known one.
- T.4: a `.circuit` graph is compiled wherever a graph is read – `edakit check`, `sim`, the gate, the circuit hash
  (its compiled data, as a TOML graph's) and `edakit graph json --write|--check`, which writes and checks the
  resolved graph.json beside it; `--map FILE` writes where each part and net was written. New: SYNC.graph, an
  error of stage G when the generated graph.json beside a TOML or a .circuit graph no longer is what its source
  resolves to; `edakit hook` runs `graph json --check` for a .circuit graph as for a TOML one.
- T.5: `edakit graph fmt [--check] [FILE …]` lays a `.circuit` source out canonically, comments kept.
- T.6: `edakit graph convert --to circuit` moves a JSON or TOML project to `hardware/graph.circuit`: flat
  statements, read back before anything is written, `[project] graph` and `edakit` set, the resolved graph.json
  beside it, the sign-offs of scope circuit carried over.
- T.7: the block library's source is `edakit/blocks/<name>.circuit`, definitions of the language; the JSON
  `block add` reads is generated from it (`python -m edakit.lang.blocks --write`) and gains `params` and
  `derivations` – led, i2c-pullups and battery-sense; `block add` reads them only with `--set` (T.8).
- T.8: derivation rules (`series_resistor`, `divider`, `pullup`, `rc`); `edakit block add --set PARAM=VALUE`
  derives a block's values and writes the record into the graph's `derivations`, `--part DES=KEY` takes an
  entry inside the window; `edakit graph derive [--write]`; `edakit graph show` lists a part's records. New
  engine DEF: DEF.derive, a warning when a part's value lies outside its record's window or the record's inputs
  changed since (grade inputs). Handbook chapter 19 begins.
- T.9: a TextMate grammar for `.circuit` files and VS Code's language configuration (`editors/vscode/`).
- T.10: handbook chapter 19, the circuit language: its forms, words and quantities, statements, definitions,
  derivations, the compiler, the hash and the commands; 3.1, 2.7 and 10 name the `.circuit` form.
- T.11: `use DEF INSTANCE (PARAM = VALUE) PORT = NET … PART = DES …` – a definition of the project's or of
  edakit's block library expanded into parts and nets, its derivations evaluated into the graph's records.
- T.12: `for VAR in A..B` – parts, nets, usages, locks, cables and layout once per value, `{n}`, `{n+k}` put in.
- T.13: `param NAME = QUANTITY`, `alias NAME = PINWORD` checked against the entry, `include PATH` – one
  namespace over the main file and the files it includes.
