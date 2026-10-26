---
name: circuit-design
description: Design a circuit or a new function from requirements – topology, parts and values – and write it into the hardware graph with building blocks, the rule catalog, the design hints and the simulation. Use when the user describes what a board or a function should do ("an Arduino Nano, five LEDs and a servo, powered by USB", "add a buzzer", "a USB-C input"), asks how to build something electrically, or starts the graph of a new project. Not for reviewing a finished design – that is the agent electrical-reviewer.
argument-hint: "<what the circuit must do>"
---

# Circuit design

Wanted: $ARGUMENTS. The graph is the only source (`${CLAUDE_PLUGIN_ROOT}/handbook/03-hardware-graph.md`); how rules,
hints and blocks fit together: `14-design.md`.

You design the circuit; you neither sign it off nor lay out the board. The second opinion is the agent
electrical-reviewer in its own session – a design reviewed by its designer has not been reviewed. The layout is the PCB
designer's, in a session of its own that gets only what you write down (section 7).

## 1. Requirements

Collect them before choosing parts: the supply (source, voltage range including unloaded and reversed, the current it
allows, the minimum load of a power bank), every input and output and what drives or reads it, the MCU or main part,
quantity and assembly (JLCPCB SMD, hand-soldered), enclosure and what a person touches, and what matters to the user
(cost, looks, robustness, loudness …). Default what you can; ask the rest in **one** decision round (skill
decision-round), not one question after the other.

## 2. Building blocks first

`edakit block list`, `edakit block show <name>`: a block brings checked parts and a topology that passed the checks
and the simulation – supply input, reverse polarity, USB-C, LED, button, I2C pull-ups, transistor switch. Add one with
`edakit block add <name> --as <INSTANCE> --connect <port>=<NET> … --dry-run`, then without `--dry-run`. A port joins
an existing net or creates it; create the MCU's signal net first (e.g. `LED_STATUS` with the MCU pin). The block's notes
say what is left: values, sim.json, edakit.toml.

## 3. Parts and pins

- Only parts with a parts entry: the project's, the block library's, or new ones through the skill part-search. Pin
  numbers and names come from the entry, never from memory or from a similar part's datasheet.
- Prefer parts the project uses already, Basic parts, parts in stock.
- MCU pins: read the entry first – strapping pins (`strap`), input-only pins (`type: input`), notes (`hint`, e.g. an
  ADC that does not work with WiFi). Buttons, LEDs and pulls stay off strapping pins unless they agree with the boot
  level (G-12).

## 4. Values are computed

Every value with formula and numbers in the component's notes: `R = (5 V − 2.0 V) / 10 mA = 300 Ω → 330 Ω`. Defaults
come from the rule catalog (`edakit rules G-11` for I2C pull-ups, `G-4` for pulls, `G-14` for USB-C) and from the
datasheets, not from memory. If you rely on a rule that is not in the catalog, say so in the notes and report it as a
check candidate (handbook 14.4) – do not present it as an established check.

## 5. Into the graph

Nets with worst-case voltage ranges `v`. Decisions numbered (D-…) in the decision log and cited in `notes`. sim.json:
sources, supplies at their limits, loads with the MCU's outputs, inputs, LEDs on, buttons, relays.

## 6. Check loop (seconds)

```bash
edakit check 2>&1 | cat     # 0 errors: fix the cause; waive only with a reason that holds
edakit hints 2>&1 | cat     # each open hint: handle it, or write down why it does not apply
edakit sim 2>&1 | cat       # every scenario passes
edakit schematic draw 2>&1 | cat   # the circuit as a drawing (SVG) for the user to look at – no EasyEDA needed
```

A hint that is taken care of gets a line in the graph: `"hints": {"H-1": "C1 1000 µF next to J1"}`.

## 7. Hand over

What you know about the board goes into the graph as `layout` – the PCB designer gets nothing else, and the plan check
holds the layout to it (L-12, handbook 7.4):

```json
"layout": {"fixed": ["SW1", "D2"], "edge": ["J1"], "near": {"R1": "U2"},
           "loops": [{"a": "C5.1", "b": "U3.2", "max_mm": 8, "what": "buck input loop"}],
           "notes": ["D2 to D9 form the bar: one row, in this order"]}
```

- `edge`: what is plugged in from outside. `fixed`: what a person presses or looks at, and parts with a mechanical
  constraint from the enclosure.
- `near`: helpers that belong to a pin – a current-setting resistor, a crystal and its capacitors, ESD protection at
  its connector, a feedback divider. The decoupling capacitor of every IC is derived, no line needed.
- `loops`: the hot loop of a switching regulator (pads of one net, checked on the routed board by L-11).
- `notes`: everything else the layout must know and no program checks – the layout review reads it.

```bash
edakit check 2>&1 | cat      # G-1 also checks the names in layout
edakit handover 2>&1 | cat   # the hand-over as the PCB designer will read it
```

The agent electrical-reviewer reviews the circuit and the hand-over; its findings go into a decision round. Then the
PCB designer takes over in a session of its own: skill pcb-round, starting with `edakit handover`. Without a PCB (a
development board and hand wiring) the drawing is the schematic, and the project is done without EasyEDA.

## Report

Requirements as understood, blocks and parts used, computed values, open decisions, results of check, hints and sim,
check candidates, where the drawing is, the hand-over (`edakit handover`).
