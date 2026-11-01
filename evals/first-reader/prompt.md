---
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

You have never seen edakit. The current directory holds its start page (`README.md`), its entry pages (`docs/`) and
the example of its walkthrough (`examples/coin-cell-led/`). Follow the documentation, and only the documentation, to
the first finding on the example: run what it says (on Linux pipe the output: `edakit check 2>&1 | cat`), then say in
three sentences which finding edakit reported, what it means and why it is accepted. Do not change any file.
