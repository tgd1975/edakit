# 20 The circuit language

For you if a circuit repeats itself, comes in variants, or has values that follow from a rule – an LED's series
resistor, a divider, a pull-up. After this chapter you can write a project's graph as `.circuit` source, compile and
check it, format it, move a JSON or TOML project to it, and derive a block's values. The notation in full is
[circuit-dsl-language.md](../docs/concepts/new/circuit-dsl-language.md); this chapter grows with the steps of
[circuit-dsl-toolchain.md](../docs/concepts/new/circuit-dsl-toolchain.md).

## 20.1 One graph, three forms

A project writes its circuit in one of three forms, named by `[project] graph` in edakit.toml: the JSON graph, the
TOML graph (3.1), or the language – `hardware/graph.circuit`. The compiler turns the language into the resolved graph
in today's JSON format; the engines, the simulation, the gate, the schematic, the firmware contract and the project's
scripts read it unchanged. Like the TOML form's, the resolved graph is generated beside the source as
`hardware/graph.json`, committed, and checked for drift.

The language is declarative and finite: definitions, usages, loops over integer ranges, named derivation rules and
variants as differences – no conditionals, no free expressions, no file access. A compile is a function from the
source and the parts entries to the resolved graph; the same input gives the same bytes. Behaviour stays in the parts
entries, layout in the board files, the checks in the engines: the language composes and decides nothing an engine
decides. The regulatory review reads the resolved graph's `purpose` as it reads a JSON graph's – support, not legal
advice (chapter 15).

| File | Role |
| --- | --- |
| `hardware/graph.circuit` | the source, named by `[project] graph` |
| `hardware/graph.json` | the resolved graph, written by `edakit graph json --write`; in no hash |
| `edakit/blocks/<name>.circuit` | edakit's blocks as definitions; the JSON beside each is generated from it |

Encoding UTF-8, lines ending in LF, no tabs; `edakit graph fmt` writes lines of at most 118 characters.

## 20.2 Words, strings and quantities

A statement starts at the first column with a keyword; lines indented deeper belong to it. `def`, `for` and
`variant` own their indented lines as a body, one level deeper; every other statement takes them as continuation
lines. `#` starts a comment, outside quotes. A word is a run of characters without blanks, `"` and `#` – `+5V`,
`U1.3V3(OUT)`, `LIM.v`, `4k7`; a `(` inside a word extends it to its `)`. A string is `"…"` with `\"` and `\\`; a line
break inside reads as one space, so a long text runs over continuation lines.

A pin word is `DES.WORD`: the part's designator, a dot, and the pin's number, name or role, read as the Design reads
every pin word (3.1, a pin by number, name or role). A word that names no pin is a compile error with the candidates
– stricter than the TOML form, which leaves it to STRUCT.pin. A pin whose name holds `#` (`OE#`) is written by its
role or number.

| Form | Examples | Meaning |
| --- | --- | --- |
| number, multiplier, unit | `330Ω`, `4k7`, `2R2`, `100nF`, `22 µF`, `10 mA`, `16 MHz` | the multiplier may stand for the decimal point |
| range | `0..5.5 V`, `2 mA .. 15 mA`, `0 V` | both ends in one unit, which may stand on the second only |
| tolerance | `10 mA ± 20 %`, `3.3 V +/- 5 %` | the range `x·(1−p)` to `x·(1+p)` |

Units: `V A W Ω F H Hz °C s m %`, with `ohm`, `ohms` and `R` for Ω; multipliers `p n u µ m k M G`. A plain number where a
unit is expected takes that unit; a lone `m` is the metre, `mA` milli. A bare number at one end of a range takes the
other end's unit but not its multiplier, so `2..15 mA` is refused – write `2 mA..15 mA`.

## 20.3 The statements of a graph

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

A part's attributes are the graph's keys (3.1), each read by its kind: `no-bom` for `bom: false`, `off_board` alone
for true, a key unknown to the attribute table an error that names the nearest one. A part's pin map is written only
where it differs from its entry's; `alias led1 = PD6` gives a module's pins the project's names, replaced before the
words are read.

## 20.4 Definitions and the block library

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

`@in` gives a net the range of the net its port joins; `{as}` passes through to `block add`. The 26 blocks of 14.5
are written so, in `edakit/blocks/<name>.circuit`, and the JSON `block add` reads is generated from them – `python -m
edakit.lang.blocks --write`, held to the sources by a test. A definition's errors are compile errors: a port that is
none of its nets, a part or net twice, a derivation whose target it does not have.

## 20.5 Derivations

A derivation is a rule of edakit's that derives a part's value from the parameters, the ranges of the nets it is
bound to and the entries of the parts: the series resistor of an LED from its current, a divider from its output
voltage and current, a pull-up from the bus. The rule proposes, the designer chooses: it never writes a value no entry
has, and the part keeps the value it is given.

```bash
edakit block add led --as STATUS --connect in=SIG --set i=4mA
edakit block add led --as STATUS --connect in=SIG --set i=2mA --part R1=C17630
```

`--set i=4mA` evaluates `series_resistor` with the block's own entries and the range of the net `in` joins (SIG,
0…3.4 V): derived 140 Ω, E24's nearest 150 Ω, the window 130…160 Ω. The block's 150 Ω fits and stays. Where the block's
value lies outside, `add` stops and names the window and the entries of the same kind and package inside it, from
the library and the project; `--part R1=KEY` takes one – its LCSC number, part number, value and pin map. A value no
entry has is never written: the part-search skill finds one.

The record goes into the graph's `derivations`, in a TOML graph as a `[[derivations]]` table: the rule, its inputs
with where each number came from, the derived value, the series' nearest value and the window, the chosen value and
what it predicts. `edakit graph show R3` lists it. `edakit graph derive` evaluates every record again with the entries
as they are now, and `--write` rewrites those of a JSON graph.

The engine DEF holds the part to its record; it compares numbers only and never evaluates a rule:

<!-- edakit:generated table DEF -->
| Code | Title | Severity |
| --- | --- | --- |
| [`DEF.derive`](../docs/catalog/def.html#DEF.derive) | derived values within their window | warning, inputs: warning |

Rule, why, fix and sources of each: `edakit explain CODE`, or the code on its page of the catalog.
<!-- edakit:end -->

The rules, generated from their table (`edakit/lang/rules.py`), each choosing from an E-series of IEC 60063:

<!-- edakit:generated rules -->
| Rule | Inputs | Output and formula | Series, window |
| --- | --- | --- | --- |
| `series_resistor` | `i` (the LED current; a range gives its centre), `led` (the LED – the one of the definition), `in` (the driving port – the one besides gnd; v_on is its range's upper bound) | value: vf(i) = vf_typ_v + rs_ohm·(i − vf_at_a); R = (v_on − vf(i)) / i | E24; one step of the series around the derived value |
| `divider` | `v_out` (the output voltage), `i` (the divider's current), `in` (the port whose range's upper bound is v_in) | top, bottom: R_bottom = v_out / i; R_top = (v_in − v_out) / i | E24; one step each |
| `pullup` | `v` (the supply: a port's upper bound or a quantity), `i_sink` (the sink current – the I2C table's), `v_ol` (the low level – the I2C table's), `c_bus` (optional), `t_rise` (optional) | value: R_min = (v − v_ol) / i_sink; R_max = t_rise / (0.8473 · c_bus), else the table's r_max_ohm; the value nearest √(R_min · R_max) | E24; [R_min, R_max] |
| `rc` | `f_c` (the corner frequency), `c` (optional), `r` (optional) | value: R = 1 / (2π f_c C), C = 1 / (2π f_c R) | E24 for a resistor, E6 for a capacitor; one step |
<!-- edakit:end -->

## 20.6 Usages, loops and parameters

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

## 20.7 Variants and requirements

A variant is a project of its own whose source names its base, the main file or another variant:

```text
variant smd of ../../hardware/graph.circuit
  part C1 capacitor "RVT1C102M1010 1000uF 16V SMD" lcsc C3359 bom yes
  use led step1 D = LED5 KT-0805G lcsc C2297 bom yes "0805 LED, green, countdown step 1"
  for n in 1..5
    part R{n} resistor "330 Ω 1/4 W metal film, THT" lcsc C58608 no-bom
  net LED_G2 without U1.led2
  accept HINT.bulk -
```

A statement that names a part, a usage, a net or a parameter of the base redefines it: what is given replaces the
base's, the rest is inherited; a part a base usage binds is redefined by its designator; `bom yes` sets the default
back; `without` takes pins off a net; `accept KEY -` removes an accept. Everything else is added. A variant never
removes a part.
Its `[project] parts` is a list, its own folder first: `["hardware/parts", "../../hardware/parts"]`.
Its resolved graph is complete, and its circuit hash takes the entries it uses, so a change of the base reaches it
only where it reaches its circuit. `edakit hook` runs every variant whose files or the main project's `hardware/` a
commit touches.

The language replaces the graph only. What else a project has stays the variant's own, beside its source: its
`edakit.toml`, the board files its `[boards]` name, `schematic.toml`, `sim.json`, the firmware – copied from the base
to start with – and a sign-off file of its own: the base's sign-offs were given for another circuit and do not carry
over.

Requirements may be written in the notation, in a file of `[project] requirements` – never in the graph's source:

```text
need N-1 "The countdown is visible across the room." who owner status accepted
requirement R-3 from N-1 must "Every countdown LED carries 2 to 15 mA while its step is on."
  subject led
  require D.i within 2 mA .. 15 mA
  verify rows "LIM.i *"  verify rows "SIM.state *"
```

`subject` names the part, net, usage or definition it is about; `require` states the condition, checked for its form
and kept as text – `verify` names what tests it. A part or net answers with `satisfies R-3` and cites a decision with
`decision D-8`; DOCS.ref resolves all of them (10.4).

## 20.8 What the compiler does

`edakit graph json` reads the source and writes the resolved graph; every phase collects all its errors before it
stops, each as `PATH:LINE: TEXT`. The phases: read the statements; check the names across the project – a
designator, a definition, a parameter or an instance twice names both places –; apply a variant's chain; put in the
parameters; expand the loops and the usages; read every pin word through the parts entries and the Design; evaluate
the derivations; assemble the graph in today's key order. A compile error stops `edakit check`, `sim` and the gate as
a broken TOML graph does, with file and line.

The compiler reads no simulation config, no board file and no sign-off; it writes no parts entry – a part without
one whose pins are named by word is an error that names `edakit part add KEY` – and allocates no designator.

## 20.9 The resolved graph and the hash

The resolved graph is the JSON graph of 3.1 in every key, plus `derivations` where the source has derivations. The
circuit hash takes the compiled data as the TOML form takes a TOML graph's – arranged, `[release] hash_ignore`
applied, `purpose` whole –, so a comment, a blank line or a statement moved changes nothing, a changed pin or value
does. `graph_sha256` names the source's bytes. The generated `graph.json` is in no hash.

`edakit graph json --check` exits 2 and lists what differs when the committed file is not what the source compiles
to; `edakit hook` runs it before each commit (2.7). `edakit check` reports the same as SYNC.graph, an error of stage
G, for a TOML graph as for a language one; a generated file not written yet is the hook's to report.

## 20.10 SysML v2 and KerML

```bash
edakit graph sysml [--out DIR]     # <artifacts>/sysml/: <project>.sysml, <project>.json, Electrical.sysml
edakit graph kerml [--out DIR]     # <artifacts>/kerml/: <project>.kerml, <project>.kerml.json, Electrical.kerml
```

The exports write a project in the standard's terms, for a SysML tool of its reader's own: a package with the circuit
as a part definition specializing `Electrical::Circuit`, every component a part usage with its pins as ports – named
by the entry's names, with number and role –, every net an n-ary connection between them with its range, cables,
accepts, locks, the layout and derivation records as metadata, the definitions of the source as part definitions of
`Block`, their usages as part usages typed by them, a variant as a specialization of its base's circuit with what
differs redefined, and the requirements as requirement usages with `satisfy`.

A requirement's `from` is a `#derivation connection` of the standard's RequirementDerivation library, one per
original with its derived requirements as the other ends; KerML, which has not that library, writes a `dependency`
per pair.

Quantities are written in base SI units, `0.01 [SI::A]`; a name that is no identifier or a keyword is quoted, `'+5V'`.

`edakit/lang/library/Electrical.sysml` is the electrical library every export imports: pins, components by type,
nets, cables, blocks, the circuit, its metadata, requirements and the rules as calculation definitions. The kernel
view, KerML, writes the same tree with KerML's keywords; it has no requirement, so a requirement is a feature there.
The JSON beside each is an array of elements with a stable `@id` (UUID 5 of the project and the qualified name),
`@type` and their relationships.

The library and the exports are read by a standard reader in a test of their own (`pytest -m sysml`, the optional
dependency group `sysml` with Syster's `systree`), against the standard library of SysML v2 where `SYSML_STDLIB` names
its folder `sysml.library`, an optional job of the CI that loads the release 2025-12; a graphical tool's import is no
test of edakit's. That reader resolves types, not imports, metadata names or the ends of a derivation – the test
holds those names to the standard library's text.

## 20.11 Commands

| Command | What it does |
| --- | --- |
| `edakit graph json [--write\|--check] [--map FILE]` | the resolved graph; written beside the source; drift; the source map – where each part, net, lock and accept was written |
| `edakit graph fmt [--check] [FILE …]` | the canonical layout, comments kept; `--check` exits 2 at the first line that would change |
| `edakit graph convert --to circuit [--dry-run]` | a JSON or TOML project moved to `hardware/graph.circuit`: flat statements, read back before anything is written, `[project] graph` and `edakit` set, the circuit sign-offs carried over |
| `edakit graph derive [--write]` | every derivation record evaluated again |
| `edakit block add NAME … --set P=V [--part DES=KEY]` | a block's derivations run (20.5) |
| `edakit graph sysml\|kerml [--out DIR]` | the project as SysML v2 or KerML (20.10) |

A converted project needs the edakit that reads the language: `[project] edakit` names it, and an older plugin says
so at the session start (STRUCT.edakit).

## 20.12 The editor

`edakit lsp` is the language server, over stdio, for a person in an editor – a model edits through the command line
and `graph show` and needs none of it. It answers the reader's and the compiler's errors as they are typed, the
findings of the graph engines at the statements they come from (through the compiler's source map, `--map`), go to
definition – a pin word to its parts entry, a usage to its definition, a net to its first statement, an include to
its file –, hover with a part's entry, a pin's number and role and a net's range, completion of pin words after
`DES.`, of codes after `accept` and of definitions after `use`, and formatting.

It needs edakit's extra `lsp` (`pygls`); without it the command says so.

`editors/vscode/` is the extension for VS Code: the TextMate grammar and the language configuration – generated
from the reader's keywords, `python -m edakit.lang.grammar --write` –, the server's client, format on save through the
server, and the commands `graph json --write`, `graph json --check`, `graph show` for the word under the cursor and
`graph fmt`, the two graph commands also as tasks. The setting `edakit.command` names the executable. It is not
published; `npm ci && npm run compile && npx @vscode/vsce package` builds it, `code --install-extension` installs it,
and an optional job of the CI compiles it.
