# easyEDAAutomation – edakit

**From a JSON hardware graph to a released, manufacturable PCB with EasyEDA Pro, driven by Claude Code.**

You describe the circuit once – parts by LCSC number, pins, nets with voltage ranges – in a JSON *hardware graph*.
edakit checks it with rules, simulates every operating case with ngspice, generates the schematic in EasyEDA Pro,
brings parts and nets into the PCB without dialogs, places the fixed parts from a plan, routes with Freerouting,
pours, prints the silkscreen, and releases the Gerber, BOM and pick-and-place files for JLCPCB only after a gate has
checked them – against the graph, on the exported files themselves. Nobody draws a wire by hand; everything in the
EasyEDA project is generated and can be regenerated.

It comes as a **Claude Code plugin** (skills, agents, the pinned EasyEDA MCP server, a hook that lets parallel
sessions share EasyEDA) and as a **Python command line** (`edakit`), plus a **handbook** that explains what, how and
why – including the ~25 EasyEDA API behaviours that cost us time.

```text
 parts database ──► hardware graph ──► schematic ──► PCB ──► manufacturing files ──► JLCPCB ──► acceptance
   (P)              (G, E)             (S)          (L)      (F)                     (M-2)       (M-4)
```

## Install

In Claude Code:

```text
/plugin marketplace add tgd1975/easyEDAAutomation
/plugin install edakit@easyeda-automation
```

Needed besides: EasyEDA Pro desktop, Node 24, [uv](https://docs.astral.sh/uv/), ngspice. Freerouting downloads itself
on Linux x64. Then build and import the patched bridge extension once and start EasyEDA unthrottled –
[handbook/02-setup.md](handbook/02-setup.md).

Without Claude Code: `uvx --from git+https://github.com/tgd1975/easyEDAAutomation edakit <command>`.

## Use

```bash
edakit doctor                   # tool chain ready?
edakit check                    # rule checks on the graph (P, G) – < 1 s
edakit sim                      # ngspice: every supply x load x tolerance corner (E) – seconds
edakit schematic create --save  # template schematic from the graph
edakit schematic layout --save  # readable board schematic: blocks, wires, GPIO table
edakit pcb parts --write        # parts into the PCB, no "Import Changes" dialog
edakit pcb apply                # outline, holes, tooling holes, fixed parts from the plan
edakit pcb autolayout           # the small parts
edakit route all                # Freerouting -> EasyEDA, pours, reload, DRC
edakit silk apply               # designators where there is room, silkscreen check
edakit gate --easyeda           # release gate: protocol, manifest, files for JLCPCB
```

In Claude Code the skills do the orchestration: `/edakit:new-project`, `/edakit:start`, `/edakit:hardware-change`,
`/edakit:part-search`, `/edakit:pcb-round`, `/edakit:release`, `/edakit:decision-round`; the agents
`electrical-reviewer` and `pcb-reviewer` do the independent reviews whose results are the sign-offs.

Start with the example: [examples/led-bar](examples/led-bar/) – a Pico 2 driving eight LEDs through a TLC5916, with
graph, parts, simulation scenarios, placement plan and sign-off file. `edakit check` and `edakit sim` run offline.

## What is in here

| Path | Content |
|---|---|
| [handbook/](handbook/README.md) | the approach, setup, graph, parts, simulation, schematic, PCB, release gate, EasyEDA API notes, reference, working with Claude, troubleshooting, lessons learned |
| [edakit/](edakit/) | the Python package: checks, simulation, EasyEDA client, schematic, PCB, routing, Gerber analysis, silkscreen, export, release gate, EasyEDA claim |
| [edakit/easyeda/](edakit/easyeda/) | `mcp-server.sh` (pinned easyeda-mcp-pro with safe defaults), `bridge-extension-patch.sh` |
| [skills/](skills/), [agents/](agents/), [hooks/](hooks/hooks.json), [bin/](bin/) | the Claude Code plugin |
| [examples/led-bar/](examples/led-bar/) | a complete small project |
| [tests/](tests/) | negative tests: every check seen red once |

## Status and limits

- Grown on one real project (EasyEDA Pro 3.2.206, easyeda-mcp-pro 1.4.0, Linux) and then made generic. The offline
  parts (checks, simulation, DSN/Freerouting/check, Gerber analysis, the board and manufacturing checks) are verified
  against that project's data; the EasyEDA-writing commands are ports of scripts used there daily.
- Two copper layers. Rectangular or polygonal outlines with straight segments (arcs as point lists).
- The simulation is DC operating points; transients are left to the acceptance test.
- The MCP server cannot order, by design.
- Used components and their licences: [easyeda-mcp-pro](https://github.com/oaslananka/easyeda-mcp-pro) (PolyForm
  Noncommercial 1.0.0 – check before commercial use), EasyEDA Pro (proprietary), Freerouting (GPL-3.0), ngspice (BSD).
  None of them is bundled.

## Licence

MIT – see [LICENSE](LICENSE).
