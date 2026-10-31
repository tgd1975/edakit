# 1 The approach: one source, generated EDA, a check at every hand-over

## The idea in one paragraph

The circuit is written down once, as a JSON **hardware graph**: every part with its LCSC number and pins, every net
with its pins and voltage range. Everything else is **generated** from it and **checked** against it – the rule
checks, an ngspice simulation of every operating case, the schematic in EasyEDA Pro, the parts and nets of the PCB,
the bill of materials, and in the end the Gerber files that go to the manufacturer. Nobody draws a wire by hand.
A change starts in the graph and flows through the same pipeline again. A **release gate** runs every check on the
files that will actually be uploaded and writes a test protocol; only a run that says RELEASED goes to JLCPCB.
A project without a PCB needs no EasyEDA at all: checks, simulation and a drawn schematic (6.5) work from the graph
alone.

```text
 parts database ──► hardware graph ──► schematic ──► PCB ──► manufacturing files ──► JLCPCB ──► acceptance
   (P)              (G, E)             (S)          (L)      (F)                     (M-2)       (M-4)
     │                 │                  │            │          │
     │ edakit check    │ edakit sim       │ schematic  │ pcb, route, silk               edakit gate --easyeda
     └─────────────────┴──────────────────┴────────────┴──────────┴──► protocol.md + manifest.json "released": true
```

## Why not just draw it in EasyEDA?

Because the drawing is not the design, and because Claude cannot see the drawing. Claude Code works on text, with
tools. In a drawing, a wire that ends one grid step next to a pin looks connected and is not; a footprint that prints
"+" at the cathode looks fine; a net label typed "VLED" instead of "V_LED" splits a net. All of these happened or
nearly happened in the project this toolkit comes from, and each one was caught by a comparison against the graph,
not by looking.

With the graph as the only source:

- **Claude can reason about the circuit.** A JSON file with pins and nets is something a language model reads
  reliably. Checks like "every input has a driver or a pull resistor", "every IC supply pin has a capacitor" or "a
  reversed supply reaches only the anode of a blocking diode" are a few lines of Python over that file.
- **Every artifact can be regenerated.** Schematic, PCB parts, nets, tracks, pours, silkscreen – all generated. That
  is what makes the EasyEDA side safe to automate: anything broken is deleted and rebuilt, without asking.
- **Every hand-over has a comparison.** Graph ↔ schematic (SYNC.schematic), graph ↔ PCB pads (SYNC.pcb), plan ↔ PCB (SYNC.plan),
  graph ↔ copper in the Gerber files (GEO.copper), graph ↔ BOM (SYNC.bom). An error has to slip past an independent comparison
  to reach the manufacturer.
- **Changes are cheap and complete.** Swapping a part is a line in the graph plus `create → layout → pcb parts →
  route → gate`. Nothing is forgotten in a corner of the schematic.

## Principles

1. **One source.** The graph for parts, values and connections; the parts database for what the datasheets say; a
   board file per board for placement and rules; the schematic file for the blocks – `edakit.toml` says where each of
   them is. The schematic and the PCB are outputs.
2. **Generated content may be deleted.** Everything in the EasyEDA project comes from scripts. When something is off,
   delete it and generate it again – no backups, no questions.
3. **A check at every hand-over, and the last one on the real files.** The gate does not trust EasyEDA: connectivity
   is recomputed from the exported Gerber copper, the BOM is generated from the graph, the stock is asked from
   JLCPCB's catalogue.
4. **Every check was seen red once.** A check that never failed may not work. For every rule there is a negative test
   that builds the fault into a copy and expects the check to find it.
5. **Sign-offs belong to a state.** A manual check (a second datasheet review, the layout review) is recorded with
   the hash of what it checked. Change the circuit or the layout and the sign-off no longer counts.
6. **An independent agent's result is the sign-off.** Checks that need judgement – is this footprint's pin 1 really
   pin 1, is this layout manufacturable and usable – are done by a separate agent in its own session. If it says OK,
   it is signed; if not, the cause is fixed and it checks again. The human is asked for decisions, not for checklists.
7. **Decisions are numbered.** D-12, SIM.driver: written down with reason, date and alternatives, cited where they apply. A
   later session (or a later you) knows why the 18-mil tracks are below the class width and that it was accepted.
8. **Tooling over clicking.** When EasyEDA needs a click, first look for the API path (parts without the import dialog,
   pad nets directly, own DSN instead of the DSN export). A dialog that remains must be a plain OK.
9. **Every rule says why.** Each check has a catalog entry with its reason, what to do and its sources; a finding comes
   with that explanation, and a review finding that a rule could have found becomes a check (chapter 14).
10. **Roles hand over in writing.** The circuit designer and the PCB designer work in sessions of their own; what the
    layout must know is in the graph (`layout`), not in a conversation, and a check holds the plan to it (14.1).

## What it achieved

The reference project – a two-layer board with an MCU module, three LED driver ICs, about 30 LEDs, buttons, a DIP
switch, a buzzer, a concave decorative outline, about 120 parts and 98 nets, assembled by JLCPCB on one side –
went from the first graph to a released set of manufacturing files in five days (19–23 October 2026). A complete
redesign of the power concept afterwards went through graph, schematic, PCB and routing within one more day. There was
budget for one order and no prototype round, so the gate had to catch everything that would hit all boards alike.

Along the way the checks found, among others: a library footprint with "+" printed at the cathode pad (fixed by
swapping the nets in the graph), holes too tight for the leads of two parts, a pin of the generated schematic that
had drifted onto two nets, a 61-mm detour in a switching regulator's current loop, and – late, by the layout review
agent – that the gate had released a run without anyone reviewing the layout. Each became a check.

What it does not give you: a guarantee. It gives you a check for every error class you know of, an explicit list of
what is checked by judgement and by whom, and an acceptance test after delivery for what neither can see.

## How the rest of this handbook is organised

| Chapter | |
|---|---|
| [2 Setup](02-setup.md) | EasyEDA Pro, Node, the MCP server, the bridge patch, Claude Code plugin |
| [3 Hardware graph](03-hardware-graph.md) | format, conventions, the rule checks |
| [4 Parts database](04-parts-database.md) | one file per LCSC number, sourcing, sign-off |
| [5 Simulation](05-simulation.md) | ngspice from the graph, behaviour models, scenarios |
| [6 Schematic](06-schematic.md) | generate, check, copy, lay out – or draw it without EasyEDA |
| [7 PCB](07-pcb.md) | placement plan, parts without dialogs, Freerouting, pours, silkscreen |
| [8 Release gate](08-release-gate.md) | stages, sign-offs, manifest, ordering at JLCPCB |
| [9 EasyEDA API](09-easyeda-api.md) | how the API and the MCP server really behave |
| [10 Reference](10-reference.md) | edakit.toml, the board and schematic files and every command |
| [11 Working with Claude](11-working-with-claude.md) | plugin, skills, agents, parallel sessions, working agreements |
| [12 Troubleshooting](12-troubleshooting.md) | symptom → cause → fix |
| [13 Lessons learned](13-lessons-learned.md) | what cost time, what we would do again |
| [14 Designing a circuit](14-design.md) | designer and reviewer, the catalog – engines, codes, data, domains –, hints, building blocks, from a finding to a rule |
| [15 Regulatory review](15-regulatory.md) | the purpose, the EU rules, the review M-6 – support, not legal advice |
| [16 KiCad as the tool chain](16-kicad.md) | a project that draws its boards in KiCad instead of EasyEDA |
| [17 Walkthrough](17-walkthrough.md) | a coin cell, a button and an LED, from the idea to the delivered boards |
