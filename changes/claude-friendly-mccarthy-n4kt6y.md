patch
- The circuit language, step T.1 of circuit-dsl-toolchain.md: quantities with units, ranges and tolerances
  (`edakit/lang/units.py`) and the E-series E6 to E96 of IEC 60063 as a catalog table (`tables/series.toml`).
- T.2: the reader of the circuit language – `edakit/lang/tokens.py`, `model.py`, `reader.py` and the attribute
  table `schema.py`: every statement of language 5 with its file and line, every error at once.
