# Handbook: from a circuit to a manufactured board with EasyEDA Pro or KiCad and Claude Code

The guides, by station. The circuit is a result on its own; the board starts from its hand-over. New here: the
[quickstart](../docs/quickstart.md) and [how it works](../docs/how-it-works.md) come first.

## The circuit

| | Chapter | Read it when |
|---|---|---|
| 1 | [The approach](01-approach.md) | you want to know why this works the way it does |
| 2 | [Setup](02-setup.md) | you install the tool chain |
| 11 | [Working with Claude](11-working-with-claude.md) | you use the plugin, run parallel sessions, or wonder about the working agreements |
| 14 | [Designing a circuit](14-design.md) | you design a circuit, want to know what a check or hint means, or use building blocks |
| 3 | [Hardware graph](03-hardware-graph.md) | you write or change the circuit |
| 4 | [Parts database](04-parts-database.md) | you add a part |
| 5 | [Simulation](05-simulation.md) | you set up scenarios or a behaviour model |
| 15 | [Regulatory review](15-regulatory.md) | a board is sold or given away, or it transmits – support, not legal advice |

The station ends with the drawn schematic – [6.5, without EasyEDA or KiCad](06-schematic.md#65-drawn-without-easyeda)
– and the hand-over to the layout (`edakit handover`, [14.1](14-design.md#141-roles)): enough for a hand-wired build,
a perfboard or a document, or the input of the board.

## The board

| | Chapter | Read it when |
|---|---|---|
| 6 | [Schematic](06-schematic.md) | you generate or arrange schematics |
| 7 | [PCB](07-pcb.md) | you place, route, pour, print |
| 8 | [Release gate](08-release-gate.md) | you prepare an order |
| 16 | [KiCad as the tool chain](16-kicad.md) | a project draws its boards in KiCad instead of EasyEDA (`toolchain = "kicad"`) |
| 17 | [Walkthrough: a coin cell, a button, an LED](17-walkthrough.md) | you want to see every step once, on the smallest board |
| 18 | [Walkthrough 2: a 555 blinker on KiCad](18-walkthrough-kicad.md) | you draw in KiCad, run a board from cells behind a power switch, or want an IC through every step |
| 12 | [Troubleshooting](12-troubleshooting.md) | something fails |
| 13 | [Lessons learned](13-lessons-learned.md) | you want the history of edakit and what it learned |

## Reference

| | Chapter | Read it when |
|---|---|---|
| 10 | [Reference](10-reference.md) | you need a key of edakit.toml, of a board or schematic file, or a command |
| 9 | [EasyEDA API](09-easyeda-api.md) | you call the API directly or something behaves strangely |

## Reading paths

- *First time:* the [quickstart](../docs/quickstart.md) → 1 → 2 → 17 → 3 → 6 → 7 → 8.
- *New circuit:* 14 → 3 → 4 → 5.
- *Something broke:* 12 → 9.
- *Adapting to your board:* 10 → 3 → 7.
- *KiCad instead of EasyEDA:* 1 → 2 → 16 → 18 – table 16.4 says what each command does there, chapter 18 shows a
  board through it.
