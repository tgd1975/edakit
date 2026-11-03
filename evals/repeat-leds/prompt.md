---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
---

The current directory is an edakit project whose graph is written in the circuit language: hardware/graph.circuit.
Add four more indicator LEDs, each with its own series resistor, on the free pins GP16 to GP19 of U1 (today in its nc
list) – written once, as one `for` loop over the four, in the way the source already writes its eight bar LEDs. Take
the parts the block library's `led` uses (`edakit block show led`). Then `edakit graph json --write`, tell the
simulation (hardware/sim.json) that U1 drives the four nets, and work until `edakit check` and `edakit sim` report no
error. On Linux pipe the output: `edakit check 2>&1 | cat`. End with one line: `DONE: <the four LEDs' designators>`.
