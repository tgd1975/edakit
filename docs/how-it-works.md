# How it works

For everyone, once. After this page you know the steps from an idea to a board, who does each one, the words the rest
of the site uses, and what is not done yet.

![The steps of edakit, the loops back and where you decide](pictures/pipeline.svg)

## Two stations

**The circuit.** You say what the circuit must do. Claude writes it as a [hardware graph](glossary.md#hardware-graph):
parts, nets, pins, each part with its datasheet's limits. edakit checks it, simulates it and draws the schematic. The
circuit is handed over in writing. This is a result on its own: enough to wire it by hand, build it on a perfboard or
put the drawing into a document.

**The board.** From the hand-over, Claude draws the schematic and the PCB in EasyEDA Pro or KiCad, routes it and
releases the manufacturing files. A release gate checks those files, not the drawing. The order goes into a maker's
cart at JLCPCB, PCBWay, Eurocircuits or AISLER. You order and pay.

## Who does what

The [walkthrough](../handbook/17-walkthrough.md) takes the smallest board through every step. Of its 14 steps, you act
in six:

| | Step | Who |
| --- | --- | --- |
| 1 | Set up | you answer, Claude writes |
| 2 | What it must do | you and Claude |
| 3 | Parts | Claude |
| 4 | Circuit | Claude as the circuit designer |
| 5 | What the checks found | Claude proposes, you decide |
| 6 | Stock and cost | Claude |
| 7 | Drawing and hand-over | Claude |
| 8 | Reviews | reviewer agents, each in a session of its own |
| 9 | The gate without EasyEDA | Claude |
| 10 | EasyEDA project | you, once (none on KiCad) |
| 11 | Layout | Claude as the PCB designer, in a session of its own |
| 12 | Release | Claude |
| 13 | Order | Claude up to the cart, you order and pay |
| 14 | Acceptance | you, with the boards in your hand |

The walkthrough has seven decisions. Two are taste: who uses the board, and a round board. Two are money and purpose:
the assembly, and a holder soldered by hand. Three are trade-offs that Claude laid out with numbers: a red LED instead
of a green one, no reverse protection, the cell's current. The forward voltages, the cell's pulse rating, the
footprints, the files and the order form came from edakit and Claude.

## How it is checked

Claude proposes. Checks that are not Claude decide whether a proposal holds: the rules of the catalog, the simulation,
the design rules of the PCB, the gate on the exported files. Reviewers in sessions of their own judge what a rule
cannot see. You decide where a decision is due.

Every step loops back when it fails:

- **The check loop.** A [finding](glossary.md#finding) of `edakit check` or a failed scenario of `edakit sim` sends
  the circuit back to the graph. A finding is fixed, or accepted with a reason you agree to.
- **The review loop.** The electrical, regulatory and layout reviewers return numbered findings. Each one is fixed or
  decided before the [sign-off](glossary.md#sign-off).
- **The PCB round.** Placement, routing and the design rules repeat until the board is clean and its reviewer agrees.
- **The gate.** A stage of the release gate that fails sends the work back to that stage. Nothing is released while
  one fails.

## The words

The [glossary](glossary.md) has every term. These ten carry the rest of the site.

**Hardware graph.** The circuit as text: parts by LCSC number, nets with their voltage ranges, pins by name or role.
It is the one source the checks, the simulation and the drawings read.

**Parts entry.** One file per part with the limits and values from its datasheet, and the datasheet's source. A part
without an entry is not checked.

**Stage.** One step of the release gate: P parts, G graph, E simulation, S schematic, L layout, F manufacturing files.

**Code.** The name of a rule, such as `LIM.v` for a voltage within its limit. `edakit explain` gives its rule, why and
what to do.

**Finding.** What a check reports: a code, a place and what to do. It is an error, a warning or a note.

**Sign-off.** A manual check signed by a reviewer or by you, bound to the hash of the files it judged. A change to
those files makes it count no longer.

**Gate run.** One run of the release gate over every stage. It writes a test protocol and, if every stage passes, the
manufacturing files.

**Release.** The one gate run whose files may go to the maker. It is current until a newer one replaces it or it is
withdrawn.

**Domain.** A set of rules a project switches on for what it contains, such as `usb`, `radio` or `motors`. `core` is
always on.

**Building block.** A piece of circuit with checked parts, such as an LED with its resistor or a USB-C input.
`edakit block add` puts it into the graph.

**Hand-over.** What the circuit designer hands to the PCB designer in writing: the boards, the parts that sit together,
the notes for the layout. `edakit handover` shows it.

## A decision round

Where a decision is due, Claude asks in Claude Code's question form: each question with its alternatives, the
recommended one first, the consequence of each. Shortened, from the walkthrough's third decision:

```text
Claude:  3. PATH.reverse on LED_SW – a CR2032 put in upside down reaches R1 and D1. Protect against it?
         a) No protection (recommended): D1 blocks; the simulation shows 3.2 V against its rated 5 V,
            and the LED stays dark. No part added.
         b) A Schottky diode in series: costs about 0.3 V – the margin a used cell needs for 1 mA.
         c) A P-MOSFET: two more parts on a board without an IC.
You:     a
Claude:  D-3 written to docs/decisions.md; PATH.reverse accepted on LED_SW with that reason;
         a scenario "reversed/pressed" added to hardware/sim.json.
```

The answer goes into the project's decision log with its reason and date, and the code where it applies names its
number.

## What it does not give you

A guarantee. You get a check for every error class edakit knows and a list of what a reviewer judges, and by whom.
For what neither can see, there is an acceptance test after delivery. The regulatory review is support, not legal
advice: it makes no claim to correctness, and nothing in it is legally guaranteed.

## State

What runs offline and what has run live, so that you know how close it is.

- **Ordering.** edakit and the skill cart put a released board into the maker's cart and stop there. Nothing orders
  or pays. The skill ran live at all four makers up to the cart on a copy of the 555 blinker
  ([live runs](../tests/fixtures/makers/LIVE.md)). The first real order went through it: pytree's tree at JLCPCB,
  from the cart the skill filled and checked. No order has gone through `edakit cart actual` yet.
- **EasyEDA's ODB++ export.** It ran on a probe board.
- **Text that ran live in EasyEDA**, in throwaway projects:
  - the positions EasyEDA's auto-layout sets, written back into the placement plan (handbook 7.4);
  - own footprints as data in the parts entry – the Christmas bell's T-Display is one (handbook 4.5);
  - the rule set of EasyEDA's DRC, read and held to the board file, or written into EasyEDA (handbook 7.5);
  - single designators at a fixed spot (handbook 7.7).
- **Clicks left in EasyEDA.** Creating the EasyEDA project stays a click by hand until the API allows it. Each click
  edakit asks for is listed in [upstream](../upstream/README.md).
- **The circuit as TOML.** Built and tested on the examples and the reference circuits. The Christmas bell's five
  boards were released on it. A JSON graph keeps working.
- **KiCad.** Tested against a faked kicad-cli and, in CI, against KiCad 10. The 555 blinker of
  [walkthrough 2](../handbook/18-walkthrough-kicad.md) went through it to a release.
- **Where it was grown.** On one real project (EasyEDA Pro 3.2.206, easyeda-mcp-pro 1.4.0, Linux), then taken
  through the Christmas bell end to end. The offline parts are
  verified against that project's data. The commands that write into EasyEDA are ports of scripts used there daily.
- **Limits.** Two copper layers. Outlines with straight segments; arcs become point lists.
- **The simulation.** DC operating points, plus transient runs of plug, unplug and switch-over where the scenarios name
  them. Small-signal AC runs where an expectation is named and the domain audio or guitar is on. Switching spikes and
  fast edges are left to the acceptance test.
- **The MCP server cannot order**, by design.
- **Licences of what it combines.** [easyeda-mcp-pro](https://github.com/oaslananka/easyeda-mcp-pro) is PolyForm
  Noncommercial 1.0.0 in the pinned 1.6.0 – check before commercial use; upstream returned to MIT after 1.6.0.
  EasyEDA Pro is proprietary, Freerouting GPL-3.0, ngspice BSD. None of them is bundled.

## Future work

Three changes would alter how a project works. Smaller extensions and fixes are not listed here.

- **Ordering through the makers' interfaces.** Today Claude in Chrome fills a maker's pages up to the cart. Through a
  maker's API the same steps would run without a browser: the files uploaded, the quote read, the same checks on what
  comes back. You still order and pay. What each maker offers: handbook 8.4, its part "Future work".
- **The circuit in a language of its own.** A notation of edakit's own instead of the TOML graph, compiled to the graph
  the checks read. Blocks take parameters, and a variant is a few lines on top of the main circuit. A project would
  convert once. What it would be: [circuit-dsl](concepts/new/circuit-dsl.md).
- **Claude independence.** Today the plugin runs in Claude Code. Made portable, it would also run in GitHub Copilot,
  Qwen Code, Mistral Vibe and OpenCode. The model could run on your own machine, through Ollama or llama.cpp. A pair of
  assistant and model is named here only once the evals show it works. What it takes:
  [claude-independence](concepts/new/claude-independence.md).
