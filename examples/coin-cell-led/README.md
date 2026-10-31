# Example: coin-cell-led

Press the button and a red LED lights, from a CR2032 coin cell – the project of the walkthrough in
[handbook chapter 17](../../handbook/17-walkthrough.md), which tells step by step how it came about. One board,
44 × 34 mm; JLCPCB assembles the button, the LED and its resistor (Economic, top side), the coin cell holder is
soldered by hand (D-4).

| File | |
|---|---|
| [edakit.toml](edakit.toml) | the table of contents: project, board, requirements, assembly |
| [hardware/requirements.toml](hardware/requirements.toml) | two needs, two requirements with their evidence |
| [hardware/graph.json](hardware/graph.json) | 4 parts, 4 nets, the purpose, what is accepted and why, the hand-over to the layout |
| [hardware/parts/](hardware/parts/) | 4 parts entries, each signed against its datasheet |
| [hardware/sim.json](hardware/sim.json) | a fresh and a used cell × button pressed and released × the LED's corners, and a cell upside down |
| [hardware/stock.json](hardware/stock.json) | what JLCPCB said about the assembled parts on 2026-10-29 |
| [hardware/schematic.toml](hardware/schematic.toml) | the block of the drawing and its notes |
| [hardware/boards/main.toml](hardware/boards/main.toml) | the board: outline, tooling holes, placement plan, a "+" beside the holder |
| [hardware/signoff.json](hardware/signoff.json) | the manual checks: M-1 and M-6 signed by the review agents, M-5, M-2, M-4 open |
| [docs/decisions.md](docs/decisions.md) | D-1 to D-5 |
| [docs/schematic.svg](docs/schematic.svg), [docs/pcb_plan_main.png](docs/pcb_plan_main.png) | drawn by `edakit schematic draw` and `edakit pcb plan` |

Offline, from this folder:

```bash
edakit check      # 0 errors; PATH.reverse accepted (a cell upside down: D1 blocks it, D-3) and three hints
edakit sim        # 9 scenarios, 95 comparisons
edakit gate       # P, G, E pass; NOT RELEASED: M-5 open, stages S, L, F need EasyEDA
```

Not done yet: everything in EasyEDA – handbook 17.11 says what comes there.
