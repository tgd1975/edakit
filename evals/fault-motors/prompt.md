---
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

The current directory is an edakit project (edakit.toml, hardware/graph.json, hardware/parts/,
hardware/sim.json). Something is wrong with its motor circuit. Find the fault with the edakit command line (`edakit check`,
`edakit sim`, `edakit explain <code>`; on Linux pipe the output: `edakit check 2>&1 | cat`). Do not change any file.

End your answer with one line: `FAULT: <designator or net> – <code> – <what is wrong, in a few words>`.
