# Handbook: from a hardware graph to a manufactured PCB with EasyEDA Pro and Claude Code

How we work, what the tools do, and why they do it that way – including everything that cost time to find out.

| | Chapter | Read it when |
|---|---|---|
| 1 | [The approach](01-approach.md) | you want to know why this works the way it does |
| 2 | [Setup](02-setup.md) | you install the tool chain |
| 3 | [Hardware graph](03-hardware-graph.md) | you write or change the circuit |
| 4 | [Parts database](04-parts-database.md) | you add a part |
| 5 | [Simulation](05-simulation.md) | you set up scenarios or a behaviour model |
| 6 | [Schematic](06-schematic.md) | you generate or arrange schematics |
| 7 | [PCB](07-pcb.md) | you place, route, pour, print |
| 8 | [Release gate](08-release-gate.md) | you prepare an order |
| 9 | [EasyEDA API](09-easyeda-api.md) | you call the API directly or something behaves strangely |
| 10 | [Reference](10-reference.md) | you need a key of edakit.toml or a command |
| 11 | [Working with Claude](11-working-with-claude.md) | you use the plugin, run parallel sessions, or wonder about the working agreements |
| 12 | [Troubleshooting](12-troubleshooting.md) | something fails |
| 13 | [Lessons learned](13-lessons-learned.md) | you want the short version of a week of mistakes |

**Reading paths**

- *First time:* 1 → 2 → the example project ([examples/led-bar](../examples/led-bar/)) → 3 → 6 → 7 → 8.
- *Something broke:* 12 → 9.
- *Adapting to your board:* 10 → 3 → 7.
