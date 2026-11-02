---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
---

The current directory is an edakit project whose graph is written in the circuit language: hardware/graph.circuit.
Make a variant of it in variants/smd/ – its own edakit.toml (copy the project's, with `[project] parts` the list of
its own folder and the main one's) and hardware/graph.circuit starting `variant smd of ../../hardware/graph.circuit` –
in which the input connector J1 is assembled by the maker (`bom yes`) and the push button SW1 is the
TS-1187A-B-A-B's SMD twin you find in the parts library (or the same part where there is none). Run
`edakit graph json --write` and `edakit check` in variants/smd until it reports no error (`edakit check --config
variants/smd/edakit.toml 2>&1 | cat`). End with one line: `DONE: <what the variant changes>`.
