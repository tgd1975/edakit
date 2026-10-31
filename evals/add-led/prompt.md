---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill]
---

The current directory is an edakit project. Add a status LED driven by GP8 of U1 (pin U1.11, today in its nc list):
first give the pin a net of its own in the project's graph (hardware/graph.json, the file `[project] graph` in
edakit.toml names), with its voltage range `v` as the other GPIO nets have, then add edakit's building block for an
LED to it (`edakit block list`, `edakit block add led --as STATUS --connect in=<net>`), tell the simulation
(hardware/sim.json) that U1 drives the net, and work until `edakit check` and `edakit sim` report no error. On Linux
pipe the output: `edakit check 2>&1 | cat`. End with one line: `DONE: <the LED's designator> on <the net>`.
