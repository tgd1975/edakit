# edakit

**Circuit design as code.** Everything a board is made of is text in your repository: the circuit, the parts with
their datasheet sources, placement, routing rules, copper pours and silkscreen per board, every decision and every
review sign-off. Claude Code does every step from there – checks, simulation, schematic, PCB, routing, release –
through edakit and EasyEDA Pro. A change is a diff, and the release gate checks it on the files that go to the
manufacturer. What is not text yet is listed under [Status and limits](#status-and-limits).

You describe the circuit once – parts by LCSC number, pins, nets with voltage ranges – in a JSON *hardware graph*.
edakit checks it with rules, simulates every operating case with ngspice, generates the schematic in EasyEDA Pro,
brings parts and nets into the PCB without dialogs, places the fixed parts from a plan, routes with Freerouting,
pours, prints the silkscreen, and releases the Gerber, BOM and pick-and-place files for JLCPCB only after a gate has
checked them – against the graph, on the exported files themselves. Nobody draws a wire by hand; everything in the
EasyEDA project is generated and can be regenerated.

It comes as a **Claude Code plugin** (skills, agents, the pinned EasyEDA MCP server, a hook that lets parallel
sessions share EasyEDA, one that starts every session with the working agreements and the project's own scripts and
agents) and as a **Python command line** (`edakit`), plus a **handbook** that explains what, how and why – including
the ~25 EasyEDA API behaviours that cost us time.

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

**Two tool chains.** A project draws its boards in EasyEDA Pro (the default) or in KiCad 10 – `toolchain = "kicad"`
in `[project]` of edakit.toml. On KiCad edakit writes one KiCad project per board and calls kicad-cli: no bridge, no
claim, no clicks; graph, checks, simulation, plan, routing and gate are the same ([handbook 16](handbook/16-kicad.md);
tested offline and in CI against KiCad 10, the first real project is open).

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
edakit part fetch C2297         # the datasheet PDF, kept with the project and checked to be of that part
edakit part search "RGB LED 5mm common cathode"   # JLCPCB's catalogue: number, class, stock – no EasyEDA
edakit check                    # rule checks on the graph (P, G) – < 1 s, failed checks explained
edakit hints                    # design hints for the parts in the graph (bulk capacitor, debouncing, ESD …)
edakit stock                    # what JLCPCB says about the assembled parts, dated – check P-4 reads it
edakit cost                     # the order for `quantity` boards: class, fees, parts, drivers, budget
edakit order                    # assembler's BOM, a cart per other supplier, hand-assembly list for all sets
edakit rules G-11               # what a check is about, why, what to do, sources
edakit sim                      # ngspice: every supply x load x tolerance corner (E) – seconds
edakit docs --write             # values quoted in documents and schematic notes, from the design data (G-19)
edakit firmware                 # the board's firmware contract as JSON from the graph; --check reports drift
edakit req                      # what the circuit must do: needs, requirements, their evidence; req R-1: one chain
edakit schematic draw           # the schematic as SVG from graph and parts – no EasyEDA (enough without a PCB)
edakit handover                 # what the circuit hands over to the layout – where the PCB designer starts
edakit schematic create --save  # template schematic from the graph
edakit schematic layout --save  # readable board schematic: blocks, wires, GPIO table
edakit pcb parts --write        # parts into the PCB, no "Import Changes" dialog
edakit pcb place --write        # decoupling capacitors, pull resistors next to their host – offline
edakit pcb apply                # outline, holes, tooling holes, fixed parts from the plan
edakit pcb autolayout           # the small parts
edakit route all                # Freerouting -> EasyEDA, pours, reload, DRC
edakit route diagnose           # why a connection stays open: walled in, blocked by other nets, or free – offline
edakit silk apply               # designators where there is room, silkscreen check
edakit gate --easyeda           # release gate: protocol, manifest, files for JLCPCB
edakit fab diff RUN_A RUN_B     # where the manufacturing files of two gate runs differ – raster, drills, BOM, CPL
edakit release current|withdraw|verify   # the one run that may be uploaded; verify the files right before upload
edakit cart fields              # every field of the maker's order form from [order], with where it comes from
edakit cart prepare|check       # the job of the skill cart from the release; B-1 to B-7 on what it brought back
edakit cart actual              # the real cost of the order: against estimate and quote, into the fee table
```

In Claude Code the skills do the orchestration: `/edakit:new-project`, `/edakit:requirements`,
`/edakit:circuit-design`, `/edakit:start`, `/edakit:hardware-change`, `/edakit:part-search`, `/edakit:own-part`,
`/edakit:pcb-round`, `/edakit:release`, `/edakit:cart`, `/edakit:decision-round`;
`/edakit:new-project` sets a project up from an interview – boards, the maker, assembly, order, money, purpose,
firmware, documents, the project's own tools –, every key from an answer, and for a project that moves to edakit the
agent `project-surveyor` first makes the inventory of what it brings – scripts, agents, skills, hardware data,
documents, decisions –, each with where it was found, the proposal and its reason; `/edakit:cart` puts a released
board into the maker's cart with Claude in Chrome, checked by edakit, and never orders or pays;
`/edakit:requirements` writes what the circuit must do into `hardware/requirements.toml` with the user, and the agent
`requirements-engineer` reads a project's documents for it – candidates with their source, contradictions, vague
words, requirements without evidence; the agent `part-selector` finds parts at the project's distributors
(LCSC/JLCPCB, RS, Farnell, Mouser, DigiKey, Reichelt) and writes their entries; the agent `easyeda-operator` runs one
long EasyEDA step and returns only its result; the agents `electrical-reviewer`, `regulatory-reviewer` (EU law for the
board's purpose: RoHS, REACH, radio, batteries – support, not legal advice) and `pcb-reviewer` do the independent
reviews whose results are the sign-offs – each also judges the requirements its sign-off verifies. Circuit, layout and
review are separate roles: the circuit designer hands the board over in writing – `layout` in the graph, shown by
`edakit handover` and kept by the plan check L-12 – the PCB designer works from that in a session of its own, and the
session that designs does not review ([handbook 14.1](handbook/14-design.md#141-roles)).

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

- The regulatory review (M-6, [handbook 15](handbook/15-regulatory.md)) is support, not legal advice: it makes no
  claim to correctness, and nothing in it is legally guaranteed.
- Ordering ([concept](docs/concepts/new/ordering.md), [handbook 8.4](handbook/08-release-gate.md)): edakit and the
  skill cart put a released board into the maker's cart and stop there – nothing orders or pays. Built offline and
  tested on recorded data; the makers' profiles (JLCPCB, PCBWay, Eurocircuits, AISLER) are provisional until their
  forms are read on the sites, and the skill, the ODB++ export and AISLER have not run live yet.
- Not text yet ([concept](docs/concepts/new/design-as-text.md), [plan](docs/concepts/new/implementation-plan.md)):
  - the positions EasyEDA's auto-layout sets: the board file holds only the fixed parts and those `pcb place` puts
    next to their host;
  - own footprints and symbols: a part without an LCSC number points into an EasyEDA library;
  - the rule set of EasyEDA's DRC;
  - the position of single designators.

  Creating the EasyEDA project and one *Import Changes* stay two clicks by hand until the API allows them.
- The KiCad tool chain ([handbook 16](handbook/16-kicad.md)) is tested against a kicad-cli the tests fake and, in CI,
  against KiCad 10's container; no board has gone through it to a release yet (16.8 lists what the first run checks).
- Grown on one real project (EasyEDA Pro 3.2.206, easyeda-mcp-pro 1.4.0, Linux), made generic, then taken through a
  second one end to end (the Christmas bell). The offline
  parts (checks, simulation, DSN/Freerouting/check, Gerber analysis, the board and manufacturing checks) are verified
  against that project's data; the EasyEDA-writing commands are ports of scripts used there daily.
- Two copper layers. Rectangular or polygonal outlines with straight segments (arcs as point lists).
- The simulation is DC operating points, plus transient runs of plug, unplug and switch-over where sim.json names
  them (E-5); switching spikes and fast edges are left to the acceptance test.
- The MCP server cannot order, by design.
- Used components and their licences: [easyeda-mcp-pro](https://github.com/oaslananka/easyeda-mcp-pro) (PolyForm
  Noncommercial 1.0.0 – check before commercial use), EasyEDA Pro (proprietary), Freerouting (GPL-3.0), ngspice (BSD).
  None of them is bundled.

## Licence

MIT – see [LICENSE](LICENSE).
