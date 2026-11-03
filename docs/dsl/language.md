# The circuit language

!!! warning "A beta"
    The explorative DSL is not part of the released edakit: it lives on the branch `claude/friendly-mccarthy-n4kt6y`
    and works only in a project that switches it on. Its form may still change from one commit to the next.

What a `.circuit` source is made of – in a project that switches the [explorative DSL](README.md) on.

## Words, strings and quantities

A statement starts at the first column with a keyword; lines indented deeper belong to it. `def`, `for` and
`variant` own their indented lines as a body, one level deeper; every other statement takes them as continuation
lines. `#` starts a comment, outside quotes. A word is a run of characters without blanks, `"` and `#` – `+5V`,
`U1.3V3(OUT)`, `LIM.v`, `4k7`; a `(` inside a word extends it to its `)`. A string is `"…"` with `\"` and `\\`; a line
break inside reads as one space, so a long text runs over continuation lines.

A pin word is `DES.WORD`: the part's designator, a dot, and the pin's number, name or role, read as the Design reads
every pin word (handbook 3.1, a pin by number, name or role). A word that names no pin is a compile error with the
candidates – stricter than the TOML form, which leaves it to STRUCT.pin. A pin whose name holds `#` (`OE#`) is written
by its role or number.

| Form | Examples | Meaning |
| --- | --- | --- |
| number, multiplier, unit | `330Ω`, `4k7`, `2R2`, `100nF`, `22 µF`, `10 mA`, `16 MHz` | the multiplier may stand for the decimal point |
| range | `0..5.5 V`, `2 mA .. 15 mA`, `0 V` | both ends in one unit, which may stand on the second only |
| tolerance | `10 mA ± 20 %`, `3.3 V +/- 5 %` | the range `x·(1−p)` to `x·(1+p)` |

Units: `V A W Ω F H Hz °C s m %`, with `ohm`, `ohms` and `R` for Ω; multipliers `p n u µ m k M G`. A plain number
where a unit is expected takes that unit; a lone `m` is the metre, `mA` milli. A bare number at one end of a range
takes the other end's unit but not its multiplier, so `2..15 mA` is refused – write `2 mA..15 mA`.

## The statements of a graph

```text
graph led-bar version 1.0 date 2026-10-25
description "Example for edakit: a Raspberry Pi Pico 2 drives eight LEDs through a TLC5916"
purpose private market EU
  notes "An example board for edakit, built for testing."
convention v "per net: [min, max] in V over all intended operating states"

part U2 ic TLC5916IDR lcsc C90107 "TLC5916 8-channel constant-current LED driver"
  nc SDO
  notes "I_OUT = 15 x 1.26 V / R1 = 9.45 mA per output."
part R1 resistor 0805W8F2001T5E lcsc C17604 value 2k "R-EXT 2 k (sets the LED current)"
part J1 connector B2B-PH-K-S(LF)(SN) lcsc C131337 no-bom source reversible "5 V input"

net LED_SDI 0..3.4 V U1.GP3 (locked) U2.SDI fn spi.tx fn_bus LED
  accept LVL.undefined "Floating until the firmware runs, but harmless: R2 holds OE high."
net GND 0 V J1.2 U2.GND R1.2

set cables []
layout fixed SW1 D2 D3
layout near R1 U2
```

| Statement | What it writes into the graph |
| --- | --- |
| `graph NAME [version V] [date D]` | `name`, `version`, `date` – the first statement of a main file |
| `description "…"`, `purpose USE [market M] [country C]`, `convention KEY "…"` | the keys of the same name |
| `ground NAME`, `grounds NAME …`, `accept KEY "reason"`, `lock PINWORD NET` | `ground`, `grounds`, the graph's `accept`, `locks.pins` |
| `part DES TYPE PARTNO [KEY VALUE …] ["label"]` | a component: `-` for a missing TYPE or PARTNO; continuation lines `nc`, `pins N=NAME`, `alias NAME = WORD`, `accept`, `notes`, `function`, `set KEY JSON` |
| `net NAME [RANGE] PINWORD [(locked)] … [KEY VALUE …]` | a net; a later `net NAME` adds pins; `(locked)` writes `locks.pins` |
| `cable NAME FROM TO A=B … [KEY VALUE]` | a cable with its pin pairs by word |
| `layout fixed\|edge\|near\|loop\|apart\|note …` | the hand-over to the layout |
| `set KEY JSON` | any key of the graph as JSON; a dotted key reaches one level down; `graph fmt` writes a JSON too long for the line one member to a line below it |

A part's attributes are the graph's keys (handbook 3.1), each read by its kind: `no-bom` for `bom: false`, `off_board`
alone for true, a key unknown to the attribute table an error that names the nearest one. A part's pin map is written
only where it differs from its entry's; `alias led1 = PD6` gives a module's pins the project's names, replaced before
the words are read.

## Definitions and the block library

A definition is a block written in the language: its parameters with defaults, its ports with their descriptions,
its parts, nets and derivations, the codes it was checked against, its optional parts and ports, its notes.

```text
def led (i = 10 mA)
  title "LED with series resistor, driven by a signal"
  port in "the driving signal: a GPIO or a logic output"
  port gnd "ground"
  part R1 resistor 0805W8F1500T5E lcsc C17471 value 150 "{as}: LED series resistor"
  part D1 led KT-0805G lcsc C2297 value green "{as}: LED (green 0805)"
  net in R1.1
  net anode @in R1.2 D1.anode
  net gnd D1.cathode
  derive R1.value series_resistor(i)
  covers LIM.v LIM.i LIM.p
```

`@in` gives a net the range of the net its port joins; `{as}` passes through to `block add`. The 26 blocks of handbook
14.5 are written so, in `edakit/blocks/<name>.circuit`, and the JSON `block add` reads is generated from them –
`python -m edakit.lang.blocks --write`, held to the sources by a test. A definition's errors are compile errors: a
port that is none of its nets, a part or net twice, a derivation whose target it does not have.

## Usages, loops and parameters

A usage puts a definition – the project's own, or a block of edakit's library by its name – into the graph:

```text
param vlogic = 0..5.5 V
use led step1 (color = green) in = LED_G1 gnd = GND anode = LED_G1_A
  R = R4 "330 Ω 0805" lcsc C17630 value 330Ω "Series resistor LED5"
  D = LED5 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 1"
net LED_G1 vlogic U1.led1 (locked)
```

`PORT = NET` puts a port on a net of the project – a new one gets the range the definition gives the port, `@in`
resolved –, `gnd` without a binding joins the ground, `NET = NAME` names an internal net that would otherwise be
`STEP1_ANODE`, `PART = DES …` binds a part of the definition to the project's designator with its part number,
attributes and label over the definition's, and `without D1` leaves an optional part out. Every part must be bound:
the compiler renumbers nothing. `{as}` in a text becomes the instance's name.

A derivation of the project's own
definition runs at every usage; one of a library block where the usage sets a parameter it reads, as `block add`
runs it only with `--set`. `edakit block add` on a `.circuit` graph writes the usage – after the last part or usage,
before the first net – and the resolved graph beside it.

`for n in 0..7` repeats its body – parts, nets, usages, locks, cables, layout – once per value, with `{n}`, `{n+2}`,
`{n-1}` and `{n*10}` put in every word and string; one level deep. `param NAME = QUANTITY` stands wherever a quantity
is expected: a net's range, a usage's parameter. `alias led1 = PD6` gives a module's pins the project's names.
`include hardware/defs.circuit` reads another file into the same namespace, in its place and once; a designator,
net, parameter, definition or instance declared twice names both places.

## What the compiler does

`edakit graph json` reads the source and writes the resolved graph; every phase collects all its errors before it
stops, each as `PATH:LINE: TEXT`. The phases: read the statements; check the names across the project – a
designator, a definition, a parameter or an instance twice names both places –; apply a variant's chain; put in the
parameters; expand the loops and the usages; read every pin word through the parts entries and the Design; evaluate
the derivations; assemble the graph in today's key order. A compile error stops `edakit check`, `sim` and the gate as
a broken TOML graph does, with file and line.

The compiler reads no simulation config, no board file and no sign-off; it writes no parts entry – a part without
one whose pins are named by word is an error that names `edakit part add KEY` – and allocates no designator.
