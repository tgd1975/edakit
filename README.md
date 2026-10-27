# edakit

**From a JSON hardware graph to a released, manufacturable PCB with EasyEDA Pro, driven by Claude Code.**

You describe the circuit once – parts by LCSC number, pins, nets with voltage ranges – in a JSON *hardware graph*.
edakit checks it with rules, simulates every operating case with ngspice, generates the schematic in EasyEDA Pro,
brings parts and nets into the PCB without dialogs, places the fixed parts from a plan, routes with Freerouting,
pours, prints the silkscreen, and releases the Gerber, BOM and pick-and-place files for JLCPCB only after a gate has
checked them – against the graph, on the exported files themselves. Nobody draws a wire by hand; everything in the
EasyEDA project is generated and can be regenerated.

It comes as a **Claude Code plugin** (skills, agents, the pinned EasyEDA MCP server, a hook that lets parallel
sessions share EasyEDA, one that starts every session with the working agreements) and as a **Python command line**
(`edakit`), plus a **handbook** that explains what, how and why – including the ~25 EasyEDA API behaviours that
cost us time.

```text
 parts database ──► hardware graph ──► schematic ──► PCB ──► manufacturing files ──► JLCPCB ──► acceptance
   (P)              (G, E)             (S)          (L)      (F)                     (M-2)       (M-4)
```

## Install

In Claude Code in the terminal:

```text
/plugin marketplace add tgd1975/edakit
/plugin install edakit@edakit
```

The VS Code extension has no `/plugin`; there the same goes through the command line, in a terminal. With only the
extension installed, `claude` is not on the PATH – it is the binary that comes with the extension,
`~/.vscode/extensions/anthropic.claude-code-<version>-linux-x64/resources/native-binary/claude`:

```bash
claude plugin marketplace add tgd1975/edakit
claude plugin install edakit@edakit
```

To update, refresh the marketplace and update the plugin, then start a new session (VS Code: a new Claude session or
*Developer: Reload Window*):

```text
/plugin marketplace update edakit
```

```bash
claude plugin marketplace update edakit && claude plugin update edakit@edakit
```

The plugin pins no version, so every commit on `main` is an update. Auto-update for the edakit marketplace can be
switched on under `/plugin` → Marketplaces (off by default for marketplaces outside Anthropic).

Needed besides: EasyEDA Pro desktop, Node 24, [uv](https://docs.astral.sh/uv/), ngspice. Freerouting downloads itself
on Linux x64. Then build and import the patched bridge extension once and start EasyEDA unthrottled –
[handbook/02-setup.md](handbook/02-setup.md).

Without Claude Code: `uvx --from git+https://github.com/tgd1975/edakit edakit <command>`.

## Use

```bash
edakit doctor                   # tool chain ready?
edakit block add led --as STATUS --connect in=LED_STATUS   # a building block with checked parts into the graph
edakit part import C2297        # symbol pins and footprint of an LCSC number from the library – no EasyEDA
edakit part diff C17179532 C49284748   # before a swap: how the new footprint lies over the old one
edakit check                    # rule checks on the graph (P, G) – < 1 s, failed checks explained
edakit hints                    # design hints for the parts in the graph (bulk capacitor, debouncing, ESD …)
edakit rules G-11               # what a check is about, why, what to do, sources
edakit sim                      # ngspice: every supply x load x tolerance corner (E) – seconds
edakit schematic draw           # the schematic as SVG from graph and parts – no EasyEDA (enough without a PCB)
edakit handover                 # what the circuit hands over to the layout – where the PCB designer starts
edakit schematic create --save  # template schematic from the graph
edakit schematic layout --save  # readable board schematic: blocks, wires, GPIO table
edakit pcb parts --write        # parts into the PCB, no "Import Changes" dialog
edakit pcb apply                # outline, holes, tooling holes, fixed parts from the plan
edakit pcb autolayout           # the small parts
edakit route all                # Freerouting -> EasyEDA, pours, reload, DRC
edakit silk apply               # designators where there is room, silkscreen check
edakit gate --easyeda           # release gate: protocol, manifest, files for JLCPCB
```

In Claude Code the skills do the orchestration: `/edakit:new-project`, `/edakit:circuit-design`, `/edakit:start`,
`/edakit:hardware-change`, `/edakit:part-search`, `/edakit:own-part`, `/edakit:pcb-round`, `/edakit:release`,
`/edakit:decision-round`;
the agent `part-selector` finds parts at the project's distributors (LCSC/JLCPCB, RS, Farnell, Mouser, DigiKey,
Reichelt) and writes their entries; the agents `electrical-reviewer`, `regulatory-reviewer` (EU law for the board's
purpose: RoHS, REACH, radio, batteries) and `pcb-reviewer` do the independent reviews whose results are the
sign-offs.
Circuit, layout and review are separate roles: the circuit designer hands the board over in writing – `layout` in the
graph, shown by `edakit handover` and kept by the plan check L-12 – the PCB designer works from that in a session of
its own, and the session that designs does not review ([handbook 14.1](handbook/14-design.md#141-roles)).

What a project teaches goes back with `/edakit:propose-rule`: a check, hint, block or part fact as an issue here,
sealed with its SHA-256. An Action triages it – accepted and built into one pull request of rule proposals, rejected
with the reason, or a question back ([handbook 14.4](handbook/14-design.md#144-from-a-finding-to-a-check)). What a
project had to build itself because edakit could not goes back with `/edakit:propose-feature`, triaged the same way and
built into one pull request of feature proposals ([handbook 11.6](handbook/11-working-with-claude.md)).

## Example: the Christmas bell

[automatic_christmas_bell](https://github.com/tgd1975/automatic_christmas_bell) – an Arduino Nano counts down on five LEDs, then a servo rings a real bell. It is
the second board built with edakit and started as a Fritzing breadboard drawing. It was not a push-button run:

- **Gaps closed in edakit:** Taking the bell through EasyEDA showed gaps, and closing them is part of what edakit is
  today ([handbook 13.6](handbook/13-lessons-learned.md)): pin names checked against the symbols, a new project's
  default board, LEDs in a row pointing the same way, off-board loads and input levels in the simulation, and a guard
  against writing into the wrong project.
- **Manual steps:** Creating the EasyEDA project, one click on *Import Changes*, and the decisions.

Where it stands:

- **Offline:** `edakit check` 0 errors, `edakit sim` 1112 checks.
- **Schematic:** equal to the graph (17 parts, 15 nets), ERC clean.
- **PCB:** 85 × 56 mm from a placement plan, routed by Freerouting (3 vias), DRC 0, silkscreen without findings.
- **Release gate:** released. Two of its reviews failed first and were fixed:
  - **L-9:** the first Nano footprint's 0.9 mm holes were too small for the header tails; it was replaced by one with
    1.1 mm holes.
  - **M-5, the layout review:** printed texts below 1 mm and copper close to the mounting holes. Both were fixed in
    edakit itself.
- **Decisions:** `docs/decisions.md` shows the numbered-decision workflow, including two decisions the simulation
  brought up.

## What is in here

| Path | Content |
|---|---|
| [handbook/](handbook/README.md) | the approach, setup, graph, parts, simulation, schematic, PCB, release gate, EasyEDA API notes, reference, working with Claude, troubleshooting, lessons learned, designing a circuit, regulatory review |
| [edakit/](edakit/) | the Python package: checks, simulation, EasyEDA client, schematic, PCB, routing, Gerber analysis, silkscreen, export, release gate, EasyEDA claim |
| [edakit/rules.json](edakit/rules.json) | the rule catalog: every check and design hint with rule, reason, fix and sources |
| [edakit/blocks/](edakit/blocks/) | building blocks (LED, button, I2C pull-ups, transistor switch, supply inputs, USB-C) and the checked parts entries they use |
| [edakit/easyeda/](edakit/easyeda/) | `mcp-server.sh` (pinned easyeda-mcp-pro with safe defaults), `bridge-extension-patch.sh` |
| [skills/](skills/), [agents/](agents/), [hooks/](hooks/hooks.json), [bin/](bin/) | the Claude Code plugin |
| [tests/](tests/) | negative tests: every check seen red once; [tests/fixtures/led-bar/](tests/fixtures/led-bar/) is the project they build their faults into, stages L and F on a written export of its input stage ([test_fab_run.py](tests/test_fab_run.py)) |

## Status and limits

- Grown on one real project (EasyEDA Pro 3.2.206, easyeda-mcp-pro 1.4.0, Linux), made generic, then taken through a
  second one end to end (the Christmas bell). The offline
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
