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

With `[project] requirements` in edakit.toml, read the file instead of asking for the requirements yourself:
`edakit req 2>&1 | cat` (handbook 3.6). The accepted requirements are what the circuit must meet, the needs say whom
it is for; a draft is not agreed yet. What the design needs and the file does not say, or says only in a draft, goes
to the skill requirements – it asks the user and writes the file, you do not. A new function starts with its
requirement there, before you choose its parts.

Without the file, collect them before choosing parts: the supply (source, voltage range including unloaded and
reversed, the current it allows, the minimum load of a power bank), every input and output and what drives or reads
it, enclosure and what a person touches, what matters to the user (cost, looks, robustness, loudness …).

Either way you settle the MCU or main part, quantity and assembly (JLCPCB SMD, hand-soldered), and **what the board
is for**: built for oneself, given away or sold, and where – it decides which rules apply (handbook 15). What the
setup asked already (skill new-project: the graph's `purpose`, `[project] quantity`, `[release] assembly`) stands – a
change is the user's decision. Default what you can; ask the rest in **one** decision round (skill decision-round),
not one question after the other. The purpose goes into the graph:
`"purpose": {"use": "private" | "gift" | "sale", "market": "EU", "notes": "what it is, who uses it"}`.

## 2. Building blocks first

`edakit block list`, `edakit block show <name>`: a block brings checked parts and a topology that passed the checks
and the simulation – supply input, reverse polarity, USB-C, LED, button, I2C pull-ups, transistor switch. Add one with
`edakit block add <name> --as <INSTANCE> --connect <port>=<NET> … --dry-run`, then without `--dry-run`. A port joins
an existing net or creates it; create the MCU's signal net first (e.g. `LED_STATUS` with the MCU pin). The block's notes
say what is left: values, sim.json, the graph's `checks`.

## 3. Parts and pins

- Only parts with a parts entry: the project's, the block library's, or new ones from the agent part-selector (the
  requirement, the quantity and the assembly in the prompt; it searches the project's distributors in its own context
  and writes the entry) or the skill part-search. Pin numbers and names come from the entry, never from memory or from
  a similar part's datasheet.
- Prefer parts the project uses already, Basic parts, parts in stock. `edakit cost` shows what a choice costs: an
  Extended type, a "Standard Only" part or a second assembled side raises the order by more than the part itself.
- MCU pins: read the entry first – strapping pins (`strap`), input-only pins (`type: input`), notes (`hint`, e.g. an
  ADC that does not work with WiFi), what each pin can do (`functions`). Buttons, LEDs and pulls stay off strapping
  pins unless they agree with the boot level (G-12). A net that needs a peripheral says so – `fn` (`spi.tx`, `pwm`,
  `adc`, …), `fn_bus` for the nets of one bus on one peripheral instance, `pwm_hz` for PWM – and G-15 checks the pin,
  the bus and the PWM slices; a pin's function is chosen here, not when the firmware is written.
- The function of every MCU pin you use, from the MCU's datasheet: a PWM signal on a PWM channel, and PWM signals with
  independent frequencies on different PWM slices or timers; a bus on a pin of its peripheral instance (SPI, I2C,
  UART); an analog input on an ADC input – into `functions` of the entry, where G-15 reads it. On a module, only pins
  brought out on its header – the module's pinout, not the chip's. Errata of the MCU that touch the pins used.
- Every IC that is not the MCU: its supply range against the net it is supplied from (the minimum operating voltage,
  not only `vmax`), and the VIH and VIL of its inputs against the domain that drives them – a 5 V part with
  VIH = 0.7 × VCC does not read 3.3 V logic. E-3 checks both where the entry gives them (`vdd_op_min`/`vdd_op_max`,
  `vih_v`|`vih_ratio`, `vil_v`|`vil_ratio`).

## 4. Values are computed

Every value with formula and numbers in the component's notes: `R = (5 V − 2.0 V) / 10 mA = 300 Ω → 330 Ω`. Defaults
come from the rule catalog (`edakit rules G-11` for I2C pull-ups, `G-4` for pulls, `G-14` for USB-C) and from the
datasheets, not from memory. If you rely on a rule that is not in the catalog, say so in the notes and report it as a
check candidate (handbook 14.4) – do not present it as an established check.

## 5. Into the graph

Nets with worst-case voltage ranges `v`. A ground that is separate on purpose (an analog ground joined at one point)
goes into the graph's `grounds` – every other ground pin belongs on the ground net (G-16). Decisions numbered (D-…) in
the decision log and cited in `notes`. sim.json:
sources, supplies at their limits, loads with the MCU's outputs, inputs, LEDs on (`leds_on` in every load once an LED is
on no driver output, `[]` when none lights – E-4), buttons, relays. No source and no cell takes more than 1 mA back
(E-3); a cell its charger charges on purpose gets `i_charge_max_a` in its cell state. Several sources (a module with
its own USB, cells next to USB): `combine_sources` with the range of each, not combinations written by hand.
A supply that comes and goes – USB plugged and unplugged, a switch-over to cells – gets `transients` (handbook 5.2):
the plug-in, the unplug and the switch-over ramp, with the rail's lowest voltage and the inrush as `expect`; E-5 holds
the MCU above its minimum once it has started.
A board people touch (requirements: what a person touches): `touch_c` with its limit from the product's standard
(IEC 62368-1 TS1: 48 °C for longer than a minute) – E-2 holds every part with `rth_ja_k_per_w` on it to that limit.
A requirement that simulation rows verify (`edakit req`) needs its scenario here – sim.json is yours, the pattern in
its `verify` belongs to the requirements file.

## 6. Check loop (seconds)

```bash
edakit check 2>&1 | cat     # 0 errors: fix the cause; waive only with a reason that holds
edakit hints 2>&1 | cat     # each open hint: handle it, or write down why it does not apply
edakit sim 2>&1 | cat       # every scenario passes
edakit schematic draw 2>&1 | cat   # the circuit as a drawing (SVG) for the user to look at – no EasyEDA needed
```

A hint that is taken care of gets a line in the graph: `"hints": {"H-1": "C1 1000 µF next to J1"}`. Settings the checks
need go into the graph's `checks` – the pins the firmware relies on (`pin_locks`; or, where the firmware follows the
graph, the contract of `edakit firmware`, handbook 3.5, with the roles `sdi`, `sdo`, `out0` … `outN` on drivers), a
connector that can be plugged in the wrong way (`reverse_protect`). Blocks and notes of the drawing, once it should look
a certain way, go into the schematic file `hardware/schematic.toml` (handbook 10.3).

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
- `loops`: the hot loop of a switching regulator (pads of one net, checked on the routed board by L-11) – one entry
  on every net of it, the net behind the diode included; G-18 asks for them from the regulator's `hot_loop`.
- `notes`: everything else the layout must know and no program checks – the layout review reads it.

```bash
edakit check 2>&1 | cat      # G-1 also checks the names in layout
edakit handover 2>&1 | cat   # the hand-over as the PCB designer will read it
```

Two agents review in sessions of their own, side by side: electrical-reviewer the circuit and the hand-over (M-1),
regulatory-reviewer the circuit and its parts against the rules for its purpose (M-6) – before the layout, because its
findings usually change parts. Its result is support, not legal advice: say so when you report it. A project with agents
of its own (`[agents.<name>]` in edakit.toml, handbook 8.6) has them review here as well: `edakit scripts 2>&1 | cat`
shows under "Who reviews where" who reviews at the circuit review – a project agent in place of the edakit agent it
replaces (`replaces`), and the project's agents with a sign-off of scope `circuit` beside them, each after the ones its
`after` names. Their findings go into one decision round. Then the PCB designer takes over in a session of its own:
skill pcb-round, starting with `edakit handover`. Without a PCB (a development board and hand wiring) the drawing is the
schematic, and the project is done without EasyEDA.

## Report

Requirements as understood – with a requirements file, which parts meet which requirement: per R-… the parts and
values that meet it and the rows or the review that test it –, blocks and parts used, computed values, open
decisions, results of check, hints and sim, check candidates, where the drawing is, the hand-over (`edakit handover`).
