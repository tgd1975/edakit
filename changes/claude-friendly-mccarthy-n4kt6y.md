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
