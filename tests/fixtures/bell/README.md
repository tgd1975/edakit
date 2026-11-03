# The bell's sources, modeled

The Christmas bell's five configurations in the circuit language, as `docs/concepts/new/circuit-dsl.md` ("The bell's
variants as the test") models them: the main file with the alias map on U1, `param vlogic` and language 11's LED step
as a definition; `smd` and `tht` as variants of it; `esp32` as a variant of `smd` – the module swap, the alias map
replaced, `vlogic` set once, `net +5V without S1.a S2.a`; `esp32tht` as a variant of `esp32` with the through-hole parts
and the layout. The texts are the bell's at its `cfb0ab0`. Text only: the entries are the bell's, in its own
repository.

`tests/test_lang_golden.py` reads them and holds them to the canonical layout; where `BELL_ROOT` names a clone of the
bell, it writes each beside its graph and compiles it – canonically equal to the bell's graph but for what the step
adds: the five records of its derivation and the LEDs' `value`.
