# A language of its own for the circuit: what it would have to be, on which basis, and when

Status 2026-10-31: concept, asked for by the owner after the review of
[circuit-language.md](../done/circuit-language.md) deferred the language of that sketch. It answers four questions:
whether a fitting language exists already, what a language of edakit's own would have to be able to do to be worth
building, on which basis – SysML v2, KerML, an existing circuit language, or something else –, and when it would
bring value. It takes a position on each, with the alternative it sets aside where that matters; what remains the
owner's is whether and when to build it, in "When it brings value". The sources say what was read and from where.
Reviewed the same day against main at `bd227e3` and corrected: the examples in today's form of the graph (`accept`,
`locks`), the numbers of the bell and led-bar re-measured, what exists already named as existing, the questions the
review found open – where assertions run, what `block add --set` writes, the names of internal nets, four projects
and one hook – answered where they belong, and the list of decisions that closed the concept folded into the text on
the owner's word. On the owner's questions the same day: a project's source over several files with one namespace
(item 9), the requirements on SysML v2's model as well ("The basis"), and a language server with a VS Code
extension as stage 4; on the owner's word after the review's second reading, the waiting period of trigger 4 taken
out, the SysML v2 tools on GitHub – the pilot's installers, Eclipse SysON, Sensmetry's Syside, Syster's `systree`
– named in "What exists", "The basis" and stage 3, and derived values by named rules of edakit's in place of
assertions evaluated from the graph: `asserts` dropped, `derivations` as the one key the language adds, DEF over
the records only (item 4, the owner's ack of the review's recommendation). Against the yardstick: a language changes
nothing about what is text – its source and its resolved graph are text in the repository –; what it changes is
where repetition, parameters and variants are written once instead of many times.

## The short answer

No existing language fits as edakit's source. The ones that have the right shape are bound to their own compilers:
atopile's `.ato` has modules, units with tolerances, assertions and arrays, but its nets are implicit, its parts come
from a picker instead of a parts entry with roles and limits, it targets KiCad only, its language was rewritten in 2026,
and its documentation and workspace now live in a browser editor behind a sign-in. SysML v2 has the right semantics for
the layer above the circuit – definitions and usages, redefinition, variation, requirements with satisfy and verify,
units –, but no electrical semantics at all, a verbose notation and open tooling in its infancy. The Python libraries
(SKiDL, PCBDL, faebryk, circuit-synth) make the circuit a program, which edakit's tools cannot edit. The rest is
proprietary, dormant or one person's experiment.

What is worth taking: SysML v2's concepts where they fit and KerML, the kernel under them, where they do not, as the
foundation the language is defined on – the way SysML v2 itself is defined on KerML –, so that every construct has a
standard's meaning and an export to SysML v2 and KerML is mechanical; `.ato`'s ergonomics as the model for the
syntax – units with tolerances, derived values, arrays, chains –; and edakit's own resolved graph (decision 4
of circuit-language.md) as the compile target, so that every check, the hash and the reviews keep reading what
they read today.

## Where the value would come from

The review of circuit-language.md named it: a language earns its cost through what a format cannot give. In
edakit's projects that is four things.

1. **Composition.** Every project of the owner is a module plus repeated sub-circuits plus a supply: the bell is a
   Nano, five LED steps, two buttons, a servo plug with its capacitor and a base load; led-bar a Pico, a driver, eight
   LEDs, a button and a power input; the tree an RP2350-Zero, 30 LEDs on three drivers, an RGB star, a buzzer, a DIP
   switch and two supplies ORed; the pedal an ESP32, five buttons, five LEDs and a supply. edakit's 26 building
   blocks (handbook 14.5) are the definitions of such sub-circuits already – with ports, `covers`, `optional` parts
   and notes –, only that `block add` copies them into the graph. A language keeps the definition and writes the
   usage: one line per LED step instead of two parts and three nets.
2. **Repetition.** Eight LEDs on `OUT0` … `OUT7` are one statement with an index, not eight parts, eight nets and
   eight pins in `+5V`. In led-bar the eight LEDs and their eight nets are 244 lines of `hardware/graph.json`
   (`tests/fixtures/led-bar`), the pins in `+5V` not counted; in the tree 30 LEDs on three drivers.
3. **Parameters and derived values.** A block's values are fixed today – 150 Ω in `led`, "another current: another
   value of the same series" in its notes. With a parameter the definition says what the value is derived from –
   a rule of edakit's, `series_resistor` with the current as its input, that knows its corners, units and series –
   and the derivation record in the resolved graph holds the part that was chosen to it. The derivation becomes
   data that a reviewer reads, instead of a number Claude computed in its head; the check of the real current stays
   with the simulation and LIM.i, which do it today at both corners.
4. **Variants as differences.** The bell's four configurations differ in parts and texts; a variant that names the
   main file and redefines what differs is a few lines. With the resolved graph as the hashed artifact (below), a
   change of the main file voids a variant's sign-offs only when it changes the variant's resolved circuit – the
   objection of circuit-language.md against `use` falls away.

A fifth, smaller: a usage can name the requirement it satisfies and the decision it follows, `satisfies R-3`,
`decision D-8`, as attributes instead of free text in `notes`. DOCS.ref resolves N-, R- and M- numbers today and
leaves decisions unresolved by design; for `decision` it would learn the decisions file, which `[release]
publish.decisions` names already. The requirements themselves follow the circuit onto SysML v2's model, in "The
basis" below.

What a flat form keeps: everything else. TOML with names (decided 2026-10-31) is the flat, explicit form; a language is
the composed, parametric one. Both end in the same resolved graph, so a project can start flat and move when its
repetition grows.

## What exists

Read from this session on 2026-10-31; the sources at the end say what was reachable.

| Language | Kind | What it has that edakit would want | What it lacks or what binds it | State |
| --- | --- | --- | --- | --- |
| atopile `.ato` | declarative language with its compiler, a browser workspace since 2026 | read in the source of 0.15.9 (the subsection below): `module`, `component` and `interface` with inheritance, imports, `new T[n]` and templates, pins and signals, `~` and bridge chains, quantities with units, ranges and tolerances, `assert … within`, `for` behind a pragma, an ERC and design checks, interfaces whose parameters a solver fills, a picker | nets without attributes, no variants, designators from the KiCad PCB, parts from a picker, KiCad only, no simulation, Python 3.14 with a Zig core and an ANTLR parser; the compiler is the language | MIT up to 0.15.9 (September 2026) with source distributions; the 0.16 line is hosted, its docs and workspace in a browser editor behind a sign-in |
| faebryk | Python library, atopile's former core | modules as classes, interfaces, `connect`, parameters by `merge`, a picker | a program, not data; a C++ core; Python 3.12 only | archived December 2024, merged into atopile |
| SKiDL | Python library | parts, nets, hierarchical subcircuits, ERC, netlists for KiCad 5–10 and SPICE; models know Python | a program; no units, no constraints beyond ERC, no net attributes; KiCad symbols as the part model | 3.0.0 in October 2026; one maintainer since 2016 |
| PCBDL | Python library (Google) | parts and nets with `<<`, a schematic as SVG | no hierarchy, no ERC, an Allegro netlist | Apache 2.0; archived January 2023 |
| circuit-synth | Python with a JSON in the middle, KiCad | an interchange JSON "any tool can read and write" | not reachable from here; nothing more is known | unverified |
| tscircuit | TypeScript and React (JSX) | components as JSX, a circuit JSON, DSN export, SPICE, written for coding agents | a TypeScript stack; a program; a React tree as the model | MIT, active |
| JITX | commercial language | bundles, design rules, constraint-driven routing | proprietary | not reachable from here |
| codeyourpcb | a DSL of its own | `component`, `net VCC [width 0.5mm] { J1.1; U1.8 }`, `module` and `use Divider as SENSE { IN = VIN }`, imports, DRC, Gerber | no parameters; "the DSL and file format may change between versions"; no parts data model | MIT or Apache 2.0; October 2026, one author |
| PHDL | an HDL for boards (Brigham Young University, a DOE paper) | design, device, instance, net, arrays, attributes, hierarchy | dormant since about 2014, Java; the paper was not reachable from here | historical |
| SysML v2 with KerML | OMG standard, textual notation | `part def` and `part`, `port def`, n-ary `connection : Net connect (a.p, b.p, c.p)`, redefinition `:>>`, `variation` with `variant` and a selection by redefinition, `requirement`, `satisfy … by …`, `verify`, `constraint def`, `calc def`, units `60 [kg]` | no electrical semantics: no net, pin, part data, board, order; verbose; open tooling: the pilot implementation in Java and Xtext (Eclipse plugins and a Jupyter kernel, installers in the release repository), Eclipse SysON (EPL 2.0, a web tool on Sirius Web with textual import and export), Syster in Rust (MIT, alpha; its Python wrapper `systree` 0.4.4a0 on PyPI, February 2026), Sensmetry's Syside (the editor free, the Python library `syside` proprietary, 1.0.0b1 in October 2026; its open-source language server retired), ANTLR grammars; models have seen little of it | 2.0 adopted by the OMG in 2025, KerML 1.0 with it, an editorial update for ISO in March 2026 |
| Modelica | equation-based modeling language | `connect`, `replaceable` and `redeclare`, arrays, units, OpenModelica | behavior, not manufacturing data; a simulator of its own beside ngspice | mature |
| structural Verilog, VHDL | hardware description languages | modules, parameters and generics, generate, named ports; models know them | digital semantics; no units, no attributes; nets as wires | mature |
| SPICE | netlist | subcircuits, `.param`, units as suffixes; models know it | positional pins – the first finding of the sketch; no attributes | mature |
| a Python API of edakit's own | `add()` and `wire()` in `tests/reference.py` | everything a program can do; models write Python best | a program as the source: edakit's tools cannot edit it, determinism has to be enforced | exists, in the tests |

**Why none of them fits as the source.** The graph carries data no circuit language has: a net's voltage range over
all operating states, its function and bus, `accept` keyed by codes, the locks the firmware relies on, the purpose, the
boards, cables with their resistance, the hand-over to the layout; and a part is an entry with roles, limits, values
and sources, not what a picker found. In every language above these would be attributes bolted on, and the language's
own semantics – a picker, implicit nets, a React tree, equations – would stand in the way or be dead weight. The two
things worth taking are a model and a style: SysML v2's definitions, usages, redefinition and variation for the
semantics; `.ato`'s units, tolerances, derived values and arrays for the syntax.

**KerML** is the kernel SysML v2 is built on – classifiers, features, types, expressions, specialization,
redefinition, multiplicity. What it is to edakit – the foundation the notation is defined on, by the owner's rule –
is the section "KerML underneath" below.

### atopile, read from 0.15.9

The source distribution of 0.15.9 on PyPI (September 2026, MIT; read, not run) holds the grammar, the library and
the examples; its `docs/` folder holds telemetry notes only, the user documentation was on docs.atopile.io. The
language: `module`, `component` and `interface` definitions with `from` for inheritance; `import X` and `from
"file.ato" import X`; `new T`, `new T[n]` and templates `<arg=…>`; `pin 1` and `signal name`; `~` connects, `~>` and
`<~` chain through bridges, `->` retypes; quantities with units, ranges `1V to 2V`, tolerances `+/- 5%`, arithmetic;
`assert … within`, `is`, `<`, `<=`; `for x in …:` and traits behind `#pragma experiment`; docstrings. A part is a
generated `component` with traits – `is_atomic_part`, `has_part_picked::by_supplier<supplier_partno="C25819">`,
`has_designator_prefix`. Interfaces carry the parameters a solver fills: `ElectricPower` with `voltage` and
`max_current`, `I2C` with its address, `SPI`, `UART`, `USB2_0`, `USB_C`, `I2S`, `CAN`, `JTAG`, `SWD`. An ERC finds
shorted interfaces, shorted power sources, undefined voltages and incompatible interfaces; design checks such as
unique I2C addresses come on top; an equation solver (`ResistorVoltageDivider` with `v_in`, `v_out`, `current`)
derives values, and the picker chooses parts to them.

Where its model differs from edakit's: a net has no attributes – a net is what `~` joins, its name a trait or taken
from the KiCad PCB –, and voltages live on `ElectricPower` interfaces, not on nets; there are no variants, only
`builds:` in `ato.yaml` with another entry module each; designators are assigned at build and kept by reading the
existing KiCad PCB (`keep_designators`), not in the source or a lock file; parts come from the picker, not from an
entry with roles, limits and sources; `if`, `param`, `test`, `require`, `check` and `ensure` are reserved words
without grammar yet; KiCad only, no simulation.

Its state: the repository's last tag is 0.14.1004 (February 2026), PyPI has releases up to 0.15.9 with source
distributions, MIT. The 0.16 line is not on PyPI: the docs site says the docs "live in the editor now", the workspace
"runs that editor right in your browser" at app.atopile.io behind a sign-in, as is packages.atopile.io; 0.15.9's CLI
fetches a migration message from "the pre-0.16 compatibility service"; the blog names 0.16.15 with agentic layout and
routing. So the open line ends at 0.15.9 as far as is visible, and the current product is hosted. Its documentation
is copyrighted like any text; a language's syntax and ideas are not what copyright protects – edakit takes the
ergonomics, copies no text and no grammar.

## What it would have to be able to do

1. **Definitions and usages.** A definition has ports, parameters with defaults, internal parts and nets, `covers`,
   `optional` parts and notes – today's block JSON, written in the language. edakit's library and a project's own. A
   usage names the definition, sets parameters and binds `inner = outer`: a port to a net, an internal part to a
   designator with its parts entry and value, an internal net to a name, so that the BOM and the board see what they
   see today; the attributes after a part's binding belong to it until the next binding.
2. **Pins by name or role, nets first-class.** As decided for the shared part: `U1.PD6`, `LED5.anode`, a net with
   its attributes, n-ary. Where an entry's name and role of a pin disagree – the bell's `C2895549` names pin 1 `C`
   with the role anode –, the word rule of L.1 decides, the language inherits it. Internal nets of a usage are named
   as `block add` names them, `<INSTANCE>_<NET>` in capitals and a port `gnd` on the ground, unless the usage names
   them; the bell's `LED_G1_A` keeps its name only when its usage says so, and `sim.json`, `schematic.toml` and the
   board files name nets (the bell's model below).
3. **Repetition.** `for n in 0..7` over parts and nets with `{n}` in names and pin words – ranges and index
   arithmetic, nothing more.
4. **Parameters with units and derived values.** Quantities as edakit reads them already (`330Ω`, `4k7`, `100nF`,
   `0..5.5 V`; `QUANTITY` in circuit.py, `v_range`), with ranges and tolerances (`10 mA ± 20 %`, `2 mA .. 15 mA`),
   as the inputs of a derivation. A definition says what a value is derived from by naming a rule of edakit's,
   `derive R.value series_resistor(i)`: `series_resistor`, `divider`, `pullup`, `rc` and their kin are functions in
   edakit that know their inputs – the net's range on the port, the entry's fields as the entries name them, the
   parameter –, their corners, their units and the series the value comes from; a new formula is a rule proposal
   (add-rule), not a line in a project. The compiler evaluates the rule with the entries – it reads them for the
   pin numbers already – and writes a derivation record into the resolved graph as data: the rule, its inputs with
   their sources, the derived value, the series value chosen and the source line; `derivations` is the one key the
   language adds to the graph. The engine DEF reads the records only: `DEF.derive` where a part's value is not the
   value its record derives, the way STRUCT.identity holds a component to its entry. The check of the real current
   stays where it is: the simulation runs the corners of `sim.json`, SIM.state judges on and off by `led_on_min_a`,
   LIM.i holds the current to `if_max_a` – with the pin's drop and the LED's series resistance, which a one-line
   formula does not know. An unbound port and a parameter outside its range are the compiler's errors, with file
   and line. A net may take its range from a port, `v @in`, as the block JSON writes `"v": "@in"` today. Free
   expressions in the notation, `(in.v.max - D.vf_min_v) / i` evaluated by the compiler into the same record, come
   only when a project needs a formula no rule has – then with interval arithmetic and the corner semantics
   defined first. Assertions evaluated by an engine from text in the graph were set aside on 2026-10-31: they would
   carry code into the graph, duplicate SIM.state and LIM.i with a cruder model, and need corners, tolerances and
   interval arithmetic the data does not have – no resistor entry has a tolerance, a net's `v` spans its off state.
   No part picking: the designer chooses the part; the record says why. Without derivations the language would be
   smaller, and the derivation would stay in Claude's head – the third of the four values above.
5. **Variants as differences.** A variant file names its base – the main file or another variant, a chain resolved
   in order, the path relative to the project's `edakit.toml` as every path in it – and redefines parts, nets,
   parameters and texts by designator and name, takes pins off a net and sets attributes back; everything else is
   inherited, and a variant never names what its base does not. Its resolved graph is complete and is what the hash
   and the sign-offs bind to, so a change of the base voids a variant's sign-offs only where it reaches the variant's
   circuit. Complete files per variant, as today, would need nothing new and cost four times every change. What the
   bell's variants need of it is measured below.
6. **References.** `satisfies R-3`, `decision D-8` as attributes: DOCS.ref resolves requirement and sign-off numbers
   today and would learn decisions (the fifth value above); the requirements themselves, written in the notation on
   SysML v2's model, are the subsection "Requirements on the same basis".
7. **Attributes pass through.** Every key of the graph's schema is written as `key value` on a part, a net or the
   graph and reaches the resolved graph unchanged. The language has syntax only for composition; a new key of the
   schema never needs a syntax decision. What has to stand still is the shape of the graph – components, nets,
   cables, layout, locks, accept, purpose –, not its keys.
8. **Determinism and a resolved graph.** The compiler is a function from the sources to the resolved graph of today's
   format plus `derivations` (item 4), with pin numbers and the full pin maps, in a stable order; no input but the
   files, no output but the graph. `edakit graph json --write` writes it, `--check` in the pre-commit hook reports
   drift, as decided for the TOML form. A project's committed resolved graph pins its circuit against a change of
   edakit's block library: the library may move, the check says so, the user decides. Two readers, two forms: the
   model reads and edits the source, which is short because definitions, loops and variants expand only when
   compiled; the code – engines, simulation, hash, scripts – reads the resolved graph, which stays as large as
   today's JSON. Reviewers read both, the source for the intent and the diff of the resolved graph for the exact
   pins. Performance is not the reason: `edakit check` takes under a second on the reference project's 65 KB, and
   compiling a bell takes milliseconds. The reasons are that the engines do not change, that the hash and the
   sign-offs bind to a flat, deterministic form, that a rewire through a parts entry or a library change shows as
   pin numbers in a diff, that project scripts keep reading JSON, and that a fresh clone needs no compiler.
9. **Several files, one namespace.** A project's source may be one file or several: the main file includes the
   others – `include leds.circuit`, the path relative to `edakit.toml` as every path in it –, a variant names its
   base, definitions come from the project's files first and then from edakit's library, and requirements may sit in
   a file of their own and name the circuit's parts, nets and usages. The compiler reads the set as one model: one
   namespace per project, a designator, a net, a definition or an ID named twice is an error with both files and
   lines, every name resolved before anything is expanded. The variant chain is this already; the bell's model below
   uses it, the tree would split its 30 LEDs from its supply.
10. **Designators explicit.** A usage names the designators of its parts; the tool that writes a usage (`block add`)
   allocates them once, as it does today. Nothing is renumbered by the compiler: one that allocated them would need
   its previous output, and a fresh clone the committed one, for shorter usages – the BOM and the board want them
   stable.
11. **Errors with file and line, a formatter, a grammar for highlighting.** Preconditions, not costs: the sketch's
    parser found every error with its line; the rest is a day each, and the formatter and the editor grammar are
    deliverables of stage 1, not later (the toolchain below).

Not in it: behavior (SPICE models stay in the parts entries), layout (stays in the board files; a definition may carry
layout intent for its instance – `near`, loops – as the hand-over does), part picking, conditionals, loops beyond
ranges, free expressions until a project needs a formula no rule has (item 4), any I/O.

## How it could look

The sketch's statements, extended by definitions, usages, repetition, derivations and variants. The bell's LED step as
a definition, with the current as a parameter:

```text
def led (color = green, i = 10 mA) ports in gnd
  part R resistor
  part D led value color
  net in     R.1
  net anode  R.2 D.anode    v @in                     # takes the range of the net on port in
  net gnd    D.cathode
  derive R.value series_resistor(i)                   # edakit's rule: the range on in, D's vf, the series value
  covers LIM.v LIM.i LVL.threshold SIM.state …        # the block's eleven codes
```

Five usages in the bell, with the designators and parts the board has today:

```text
# Countdown: five steps, each a pin of the Nano → 330 Ω → LED → GND
use led step1 (color = green)  in = LED_G1 gnd = GND   R = R4 lcsc C17630 value 330Ω   D = LED5 lcsc C2895549
use led step2 (color = green)  in = LED_G2 gnd = GND   R = R3 lcsc C17630 value 330Ω   D = LED4 lcsc C2895549
use led step3 (color = yellow) in = LED_Y1 gnd = GND   R = R2 lcsc C17630 value 330Ω   D = LED3 lcsc C2895495
…
net LED_G1 0..5.5 V U1.PD6 (locked)      # the driving nets stay nets of the project, with their ranges
```

In a usage the words after `R = R4` belong to R until the next binding, `D =`; a usage that sets more than a part's
entry and value puts each part on an indented line of its own, as the bell's model below does.

Repetition, led-bar's eight LEDs on the driver's outputs – today 8 parts, 8 nets and 8 pins in `+5V`, 244 lines of
JSON for the parts and their nets:

```text
for n in 0..7
  part D{n+2} led KT-0805G lcsc C2297 value green "LED {n+1} (green 0805)"
  net LED{n} 0..5.5 V U2.OUT{n} D{n+2}.cathode
  net +5V D{n+2}.anode
```

A variant, the bell's SMD configuration – today a complete graph of its own:

```text
variant smd of ../../hardware/graph.circuit           # paths relative to the project's edakit.toml, as in it
  use led step1 D = LED5 KT-0805G lcsc C2297          # the 0805 LED, anode on pin 1; everything else inherited
  …
  description "… the SMD configuration"
```

The same step in SysML v2's textual notation, with an electrical library of edakit's own (`Pin`, `Net`, `Resistor`,
`LED` as definitions), as far as the grammar goes:

```text
part def LedStep {
    attribute color : LedColor = green;  attribute i : ElectricCurrentValue;
    port in : Pin;  port gnd : Pin;
    part R : Resistor;  part D : LED;
    connection : Net connect (in, R.p1);
    connection anode : Net connect (R.p2, D.anode);
    connection : Net connect (D.cathode, gnd);
}
part step1 : LedStep {
    :>> color = green;
    part :>> R { attribute :>> designator = "R4"; attribute :>> lcsc = "C17630"; }
}
connection : Net connect (u1.PD6, step1.in);
```

Two to three times the text, every edakit key an attribute, every net a typed connection usage, and a reader who has
to know SysML v2. The same in Python, the fallback (an API of edakit's own in a restricted subset: no imports beyond
it, no I/O, no randomness):

```python
for n in range(8):
    d = c.part(f"D{n+2}", "led", lcsc="C2297", value="green")
    c.net(f"LED{n}", v=(0, 5.5)) << (u2.pin(f"OUT{n}"), d.cathode)
```

Shortest, and the form models write best; but a program, which only a model can edit – `block add`, a converter, a
formatter and `graph show` need data they can read and write. That is the argument for a declarative notation.

## The bell's variants as the test

The owner's requirement: the language must cover the bell's variants. The bell has four configurations (decisions
D-11 to D-15 of its `docs/decisions.md`): main, smd, tht and esp32, each an edakit project of its own with its own
`edakit.toml`, graph, parts folder, simulation config, board file, schematic arrangement and sign-off file, one
EasyEDA board each. Measured at the bell's `059162a`, pins compared by name or role; the round trip of the sketch
holds for all four in both forms. The bell is still in the form of before the cut `4982d35` – `hints`, `waive`,
`checks.pin_locks` –; the measurements are of its data, the examples here are written in today's form, `accept` with
the HINT codes, `accept`, `locks.pins`:

| | smd | tht | esp32 |
| --- | --- | --- | --- |
| parts replaced: another entry, other texts, `bom` | 7: LED1–LED5, C1, J1 | 11: R1–R9, S1, S2 | 13: the seven of smd, LED4 and LED5 yellow-green, R1–R5 at 100 Ω, and U1 – the T-Display for the Nano: 24 pins instead of 30, other names, another `nc`, no `waive` |
| nets | the same | the same | `+3V3` added; S1.a and S2.a move from `+5V` to it; 8 nets get another U1 pin (`PD6` to `IO27` …); 13 nets' `v` go from `0..5.5 V` to `0..3.4 V`, the five anode nets among them; 4 notes change, `+3V3` brings one |
| locks | the same | the same | all 8, keyed by other pins |
| texts | `description`, `purpose.notes`, 3 hints – HINT.bulk, HINT.debounce, HINT.esd in today's form | the same | the same, and the notes of U1, R8 and R9 |
| parts entries of its own | 5 | 4 | 7 |
| statements of the sketch's language that differ from main's 59 | 25 of 69 | 21 of 64 | 70 of 83 |
| beside the graph | board, schematic | board, schematic | board, schematic, `sim.json` (the source's pins and voltages), the firmware `variants/esp32/firmware`, the library script `hardware/lib/tdisplay_device.py` |

A variant file that redefines parts and texts covers smd and tht: seven statements for smd's parts (five LEDs, C1,
J1), four for tht's (R1–R5, R6–R7, R8–R9, S1–S2 with `for`), the texts, the three accepted hints – about a
dozen lines each, written out in the model below. The esp32 variant shows what else the language needs:

1. **Module pins by function.** Eight nets and eight locks change only because the T-Display's pins have other
   names than the Nano's. An alias map on the module in the project's source – `alias U1 led1 = PD6 led2 = PD5 …
   servo = PB0 btn_start = PB4 btn_reset = PB3` – lets the nets say `U1.led1`; the variant replaces the map and the
   nets stand. The map is what the firmware relies on (`buttons.ino` names D6, D8, D11), and the locks keyed by the
   alias, `lock U1.led1 LED_G1`, are the same in every variant. Decision 6 of circuit-language.md declined an alias
   in the parts entry for the TOML form; this one lives in the project's source and describes the project's use of
   the module, not the module. Without the map a variant with another module rewrites every net and lock on it, as
   esp32 does today, 70 of 83 statements; locks keyed by the pin instead of the alias would differ in every variant
   for the same meaning.
2. **A parameter for the logic level.** `param vlogic = 0..5.5 V` in main and `net LED_G1 vlogic U1.led1 R4.1`;
   the esp32 variant sets `vlogic = 0..3.4 V` once instead of in thirteen nets.
3. **Pins taken off a net.** `net +5V without S1.a S2.a` beside `net +3V3 vlogic U1.3V3 S1.a S2.a`: a variant
   removes as well as adds. An attribute goes back to its default the same way: `bom yes` on the LEDs the assembly
   places, where main has `no-bom`.
4. **A module swap as one statement**, with its entry from the variant's parts folder, its `nc` and its alias map.
5. **A variant of a variant.** D-13 says "like the variant SMD, with the T-Display": `variant esp32 of
   ../smd/hardware/graph.circuit`, a chain resolved in order.
6. **Parts folders.** D-15 keeps every variant's parts folder complete, because the hash covers the whole folder
   (`state_hash` in release/gate.py takes every entry) and a part added for one board would void the others'
   sign-offs. With inheritance `[project] parts` becomes a list of folders and the lookup goes variant first, then
   main – a list as `[project] requirements` is one today, with a difference: the requirements files are a union in
   which a name twice is an error, the parts lookup gives the variant's entry precedence –, and the circuit hash
   covers the entries the resolved graph uses, not the folder: a part added for one board reaches no other board's
   hash, and a copy per variant is a choice, not a need.
7. **What stays per variant project:** `edakit.toml`, the board file, `schematic.toml`, `sim.json`, the sign-off
   file, the firmware. The language replaces the graph only.

The esp32 variant then, on smd as its base:

```text
variant esp32 of ../smd/hardware/graph.circuit
  param vlogic = 0..3.4 V                     # 3.3 V logic: every net written with vlogic follows (D-13)
  part U1 module "LILYGO TTGO T-Display V1.1" lcsc C18722937 no-bom "LILYGO T-Display V1.1 (plugged in)"
    nc    …                                   # the module's unused pins
    alias led1 = IO27 led2 = IO26 led3 = IO25 led4 = IO33 led5 = IO32
    alias servo = IO13 btn_start = IO38 btn_reset = IO37
    notes "Plugs into two 1x12 female headers …"
  part LED5 led KT-0805YG lcsc C2292 "0805 LED, yellow-green, countdown step 1"   notes "D-14: …"
  part LED4 led KT-0805YG lcsc C2292 "0805 LED, yellow-green, countdown step 2"   notes "D-14: …"
  for n in 1..5
    part R{n} resistor "100 Ω 0805" lcsc C17408 value 100Ω   notes "D-14: (3.3 V − 2.1 V) / 140 Ω ≈ 8.6 mA"
  net +3V3 vlogic U1.3V3 S1.a S2.a   notes "3V3 pin of the T-Display; switched to the inputs by the buttons (D-13)."
  net +5V without S1.a S2.a          notes "5V pin of the T-Display: USB VBUS behind the module's 1N5819; …"
  net SERVO      notes "IO13, 3.3 V PWM into the servo's signal input (D-13)."
  net BTN_START  notes "Pressed = 3.3 V at IO38 (input only), else R7 pulls to GND (D-13)."
  net BTN_RESET  notes "Pressed = 3.3 V at IO37 (input only), else R6 pulls to GND (D-13)."
  description "…"
  purpose notes "… The T-Display's ESP32 uses Wi-Fi (2.4 GHz, channels 1-13) … Bluetooth stays off."
  accept HINT.bulk "C1 1000 µF / 16 V electrolytic on +5V, next to J1 (it buffers the module's 5V pin)"
  accept HINT.debounce "in the ESP32 firmware like buttons.ino (50 ms); the firmware port is open (D-13)"
```

About twenty lines against 70 changed statements today, and the locks untouched. Everything a variant does is a
redefinition of something the base names – a part, a net, a parameter, a text –, which is SysML v2's `:>>` with a
syntax of the sketch's kind; nothing in it is a conditional.

## The bell's variants, modeled

How the four configurations would be written, a sketch on the bell at `059162a` in today's form of the graph. Five
source files replace four graphs – a larger project splits its main file further with `include`, item 9; the bell
has no need –; the four resolved graphs stay, generated:

```text
hardware/graph.circuit                   main: the Nano with its alias map, the LED step, five usages, the nets
hardware/graph.json                      resolved – edakit graph json --write –, committed, checked by the hook
variants/smd/hardware/graph.circuit      variant smd of ../../hardware/graph.circuit, about a dozen lines
variants/tht/hardware/graph.circuit      variant tht of ../../hardware/graph.circuit, about a dozen lines
variants/esp32/hardware/graph.circuit    variant esp32 of ../smd/hardware/graph.circuit, about twenty lines
variants/*/hardware/graph.json           resolved per variant, generated, committed, checked
```

The main file: the statements of the prototype's `bell.circuit` with this concept's constructs – a parameter for the
logic level, the module's alias map, the LED step as a definition, five usages that keep today's designators and net
names –, the parts' labels and notes shortened:

```text
graph christmas-bell version 0.3 date 2026-10-25
description "Automatic Christmas bell: an Arduino Nano counts down on five LEDs, then a servo swings a real bell. …"
purpose private market EU
  notes "… built and used by the owner – not sold or given away (D-16). …"
param vlogic = 0..5.5 V                                  # the logic level; the esp32 variant sets 0..3.4 V

part U1 module "Arduino Nano V3" lcsc C9900187880 no-bom "Arduino Nano 3 (plugged in)"
  nc TXD RXD RESET PD7 PB1 PB2 PB5 3V3 AREF PC0 PC1 PC2 PC3 PC4 PC5 ADC6 ADC7 PC6 VIN
  alias led1 = PD6 led2 = PD5 led3 = PD2 led4 = PD3 led5 = PD4    # the firmware's D6 D5 D2 D3 D4
  alias servo = PB0 btn_start = PB4 btn_reset = PB3              # D8 D11 D12 by the entry's names – the symbol's
                                                                 # swapped labels of pins 14 and 15 included
  accept STRUCT.entry "VIN stays free: the Nano runs from its USB socket"
  notes "Plugs into two 1x15 female headers, pitch 2.54 mm … its labels of pins 14/15 are swapped …"
part J1 connector PZ254V-11-03P lcsc C2937625 no-bom "Servo (GND, +5 V, signal)"
part C1 capacitor "1000uF 16V" lcsc C439782 no-bom "Buffer capacitor for the servo"
part S1 button K2-1102SP-C4SC-04 lcsc C127509 "Start button"
part S2 button K2-1102SP-C4SC-04 lcsc C127509 "Reset button"
part R7 resistor "4.7 kΩ 0805" lcsc C17673 value 4.7kΩ "Pull-down, start button"
part R6 resistor "4.7 kΩ 0805" lcsc C17673 value 4.7kΩ "Pull-down, reset button"
for n in 8..9
  part R{n} resistor "100 Ω 2512 1 W" lcsc C35218 value 100Ω "Base load for USB power banks (R8 ∥ R9 = 50 Ω)"
    notes "Keeps a power bank from switching off: the circuit alone draws 35–75 mA (D-8)."

def led (color = green, i = 10 mA) ports in gnd          # as above; or edakit's block, once it has parameters
  …

use led step1 (color = green)  in = LED_G1 gnd = GND anode = LED_G1_A     # anode = …: today's net name kept
  R = R4   "330 Ω 0805" lcsc C17630 value 330Ω "Series resistor LED5"
  D = LED5 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 1"
use led step2 (color = green)  in = LED_G2 gnd = GND anode = LED_G2_A
  R = R3   "330 Ω 0805" lcsc C17630 value 330Ω "Series resistor LED4"
  D = LED4 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 2"
use led step3 (color = yellow) in = LED_Y1 gnd = GND anode = LED_Y1_A
  R = R2 …   D = LED3 XL-504UYD lcsc C2895495 …
use led step4 (color = yellow) in = LED_Y2 gnd = GND anode = LED_Y2_A
  R = R1 …   D = LED2 XL-504UYD lcsc C2895495 …
use led step5 (color = red)    in = LED_R  gnd = GND anode = LED_R_A
  R = R5 …   D = LED1 XL-504SURD lcsc C2895493 …

net +5V       0..5.5 V  U1.5V C1.plus J1.2 S1.a S2.a R8.1 R9.1
  notes "5V pin of the Nano: USB minus its Schottky diode; supplies the servo and the buttons."
net GND       0 V       U1.GND C1.minus J1.1 R6.2 R7.2 R8.2 R9.2    # the steps' gnd ports are on it already
net SERVO     vlogic    U1.servo (locked) J1.3
net BTN_START vlogic    U1.btn_start (locked) S1.b R7.1
  notes "Pressed = 5 V at D11, else R7 pulls to GND (D-4)."
net BTN_RESET vlogic    U1.btn_reset (locked) S2.b R6.1
  notes "Pressed = 5 V at D12, else R6 pulls to GND (D-4)."
net LED_G1    vlogic    U1.led1 (locked)                 # the step's port in is on it through the usage
net LED_G2    vlogic    U1.led2 (locked)
net LED_Y1    vlogic    U1.led3 (locked)
net LED_Y2    vlogic    U1.led4 (locked)
net LED_R     vlogic    U1.led5 (locked)
```

About 50 lines against 59 statements today: the bell has little repetition, and a usage with explicit designators,
entries and labels is two to three lines. What the bell gains is below, in the variants. The smd variant, D-11:

```text
variant smd of ../../hardware/graph.circuit             # relative to the project's edakit.toml, as its paths are
  description "… the SMD configuration"
  purpose notes "…"
  part J1 connector "HX PZ2.54-1x3P TP-YQ" lcsc C41417360 bom yes     # placed by the assembly: bom back to yes
  part C1 capacitor "RVT1C102M1010 1000uF 16V SMD" lcsc C3359 bom yes
  use led step1 D = LED5 KT-0805G lcsc C2297 bom yes "0805 LED, green, countdown step 1"
  use led step2 D = LED4 KT-0805G lcsc C2297 bom yes "0805 LED, green, countdown step 2"
  use led step3 D = LED3 KT-0805Y lcsc C2296 bom yes "0805 LED, yellow, countdown step 3"
  use led step4 D = LED2 KT-0805Y lcsc C2296 bom yes "0805 LED, yellow, countdown step 4"
  use led step5 D = LED1 KT-0805R lcsc C2295 bom yes "0805 LED, red, countdown step 5"
  accept HINT.bulk "C1 1000 µF / 16 V electrolytic on +5V, next to J1 (it buffers the Nano's 5V pin)"
  accept HINT.debounce "debounced in firmware: src/firmware/buttons.ino, 50 ms (DEBOUNCE_DELAY)"
  accept HINT.esd "J1 is the servo's own cable inside the bell's frame, plugged once; no TVS – like the main board"
```

The tht variant, D-12 – a variant redefines by designator, so the resistors inside the usages are five lines of one
`for`, whichever step holds them:

```text
variant tht of ../../hardware/graph.circuit
  description "… the THT configuration"
  purpose notes "…"
  for n in 1..5
    part R{n} resistor "330 Ω 1/4 W metal film, THT" lcsc C58608 value 330Ω no-bom
  for n in 6..7
    part R{n} resistor "4.7 kΩ 1/4 W metal film, THT" lcsc C57204 value 4.7kΩ no-bom
  for n in 8..9
    part R{n} resistor "100 Ω 1 W metal film, THT" lcsc C119469 value 100Ω no-bom
  for n in 1..2
    part S{n} button K2-1102DP-C4SW-04 lcsc C110153 no-bom
  accept HINT.bulk "…"  accept HINT.debounce "…"  accept HINT.esd "…"
```

The esp32 variant is the example above, on smd as its base: the parameter, the module with its `nc` and alias map,
two LEDs, five resistors, two nets changed and one added, the notes and texts, two hints.

**What the compiler makes of it.** Each project's `edakit graph json --write` reads its source, follows the chain –
esp32 reads smd reads main –, applies the redefinitions in order, expands the usages and loops, resolves the alias
map and the pin words through the entries and writes the resolved graph in today's format. The test of stage 2: the
four resolved graphs equal the bell's four graphs of `059162a` converted to today's form (`edakit convert`), pins
by number, nets by name – which holds only because the usages bind `anode = LED_G1_A`; without the binding the nets
would be `STEP1_ANODE`, and `sim.json`, `schematic.toml` and the board files name nets.

**Four projects, one repository, one hook.** Each project keeps its `edakit.toml`; `[project] graph` names the
`.circuit` file and `[project] parts` the folders, the variant's first, then main's. A change of the main file
changes the three variants' resolved graphs wherever they inherit it, so the bell needs one step that runs `graph
json --write` in all four projects – a `graphs` target in its Makefile – and the pre-commit hook of L.5 runs
`--check` in all four; the bell has no hook today. The diff of each resolved graph shows what the change reached; a
variant's circuit hash, and with it M-1 and M-6, move only where that diff is not empty.

**What stays per project:** the board file, `schematic.toml`, `sim.json`, `signoff.json`, the firmware; all of
them name parts by designator and nets by name, which is why the usages name both.

## The basis

The semantics of SysML v2 map onto edakit's needs above the netlist and not onto the netlist itself:

| edakit | SysML v2 |
| --- | --- |
| a parts entry: kind, pins with roles, limits, values | `part def` with port usages typed by their role and attributes |
| a component: designator, LCSC number, value, board | `part` usage with attributes |
| a pin reference `U1.PD6` | a port usage of the part usage |
| a net with `v`, `fn`, `accept` | an n-ary `connection` usage typed by a `connection def Net` with attributes |
| a block: ports, parameters, parts, nets, `covers`, `optional` | `part def` with port usages and attributes as parameters |
| a usage of a block | a `part` usage typed by the block's definition, its ports connected |
| a variant project | `variation` and `variant`, the selection by redefinition `:>>` with `=` |
| a requirement R- | `requirement` usage with `subject` and `require constraint`, `satisfy … by …`; a need N- the `#original` of a `#derivation` (below) |
| a gate row, a sign-off M- | a `verification case` whose objective `verify`s the requirement, its `verdict` |
| a decision D- | documentation (`doc`); no relationship of the standard |
| `accept`, the hash, the release | nothing |
| a quantity with its unit | ISQ and SI, `10 [mA]` |

So: the model yes, the notation no. The notation is two to three times the text for a 19-part circuit, every
connection in the examples is binary and a net would be a construction of edakit's own, the electrical layer and the
manufacturing data would be attributes without meaning to any SysML tool, the free readers are the Java pilot
implementation, Eclipse SysON and an alpha in Rust while the Python library is proprietary, and models have seen
little SysML v2. What the model gives: a vocabulary that is a standard's – definition, usage, redefinition,
variation, satisfy, verify –, clean rules for what a redefinition means, and the option of an export
`edakit graph sysml` for whoever models the system around the board in SysML v2.

### KerML underneath

The owner's rule (2026-10-31): take over every concept of SysML v2 that fits; where one does not, do not bend it, go
one level down to KerML; never take the surface syntax of either. KerML is the kernel SysML v2 is built on – SysML v2
is KerML plus libraries plus a surface syntax: `part def` is a KerML structure specializing the Systems Library's
`Part`, `part` a feature, `connection` a connector. So the layers are: edakit's notation on top; edakit's electrical
library, defined in SysML v2's terms where they fit – `part def Resistor`, `port def Pin`, `connection def Net`,
attributes with the ISQ and SI units, `requirement` for R- and M- numbers, `variation` for the bell's configurations,
`calc` for derivations, metadata for `accept`, locks and decisions –; and KerML's `struct`, `feature`,
`connector`, `function` directly where SysML v2's definitions would bring a meaning that does not fit. So far none was
found: a net as an n-ary `connection` and a pin as a `port` without flows need no bending, and the occurrence
semantics SysML v2 carries along does no harm. The practical consequence of staying in SysML v2's terms: an exported
model is a SysML v2 model, and SysML tools draw it as parts, ports and connections and follow its requirements; a
model on raw KerML structures they do not. The owner would find KerML the fitting foundation; it is, in this way.

| Notation | KerML, or SysML v2's library on it |
| --- | --- |
| `def led (color = green, i = …) ports in gnd` | `struct Led :> Block` – or `part def Led :> Block` – with `feature in : Pin`, `feature gnd : Pin`, the parameters features with defaults |
| `use led step1 (…) in = LED_G1 …` | `feature step1 : Led` (`part step1 : Led`), its port an end of the net's connector |
| `part R4 resistor lcsc C17630 value 330Ω` | `feature R4 : Resistor` with attribute features `lcsc`, `value`, `board` … |
| `net GND 0 V U1.GND C1.minus …` | `connector GND : Net (U1.GND, C1.minus, …)` – n-ary, with features `v`, `fn`, `accept`; in SysML v2 a `connection` |
| `param vlogic = 0..5.5 V` | `feature vlogic : VoltageRange default …`; the unit from `SI`, the quantity from `ISQ` |
| `for n in 0..7 …` | multiplicity, `feature D : LED[8]`, indexed features |
| `derive R.value series_resistor(i)` | a feature value bound to the invocation of a `function` of edakit's library; in SysML v2 a `calc` |
| `variant esp32 of smd …` | a structure specializing the base, its features redefined with `:>>`; in SysML v2 `variation` and `variant` |
| `alias U1 led1 = PD6` | a feature `led1` of the module's usage bound to its pin feature |
| `satisfies R-3`, `decision D-8`, `accept` | `satisfy` and `verify` from SysML v2's Requirements library; `accept` and decisions as metadata |
| units, ranges, tolerances | SysML v2's Quantities and Units: `ISQElectromagnetism` has voltage and capacitance, `ISQBase` the electric current, `SI` the units |

**What the standard says about languages built on it** – KerML 1.0, adopted September 2025, the formal document
formal/2026-03-01 of March 2026, its Scope clause: "the full KerML language can be considered to be simply a
syntactic extension of the core, which is semantically extended using library models. By intent, this approach can
also be used to build on KerML to create more specific modeling languages. Application specific modeling languages
can be built on KerML by extending the KerML abstract syntax, specializing its semantics, with concrete syntaxes
similar to or entirely different from KerML's." And: "KerML can provide the kernel for a family of syntactically
diverse but semantically integrated modeling languages." Clause 10 repeats it for interchange: "KerML is intended to
be used as the basis for building other modeling languages", and a KerML-based language names a file extension for
its own textual notation, while "it shall always be possible to use JSON format as a model interchange file format"
(10.2, 10.4). Conformance (Clause 2) comes in four kinds – abstract syntax, concrete syntax, semantic, model
interchange –, and "every conformant KerML modeling tool shall demonstrate at least Abstract Syntax Conformance and
Model Interchange Conformance"; the concrete syntax is optional. So a notation of edakit's own over KerML's abstract
syntax, with the JSON interchange as its export, is what the specification itself describes, not a bending of it.

**What the standard provides, verified in the specification and the OMG's release repository:**

- The textual grammar: classifiers `classifier`, `class`, `struct`, `datatype`, `assoc`, `assoc struct`,
  `behavior`, `function`; features with typing `:`, values `=` (bound) and `:=` (initial), `default`; `:>` for
  specialization of types and subsetting of features, `:>>` for redefinition; multiplicity `[n]` and `[lo..hi]`,
  `ordered`, `nonunique`; connectors binary (`connector c : T from a to b`) and n-ary (`connector c : T (a, b, c)`,
  the ends matched in order to the association's ends, 7.4.6.2), `binding` and `succession` binary; invariants
  `inv { … }`, `inv false` for a negated one (7.4.8.5); expressions with `if … ? … else …`, arithmetic,
  comparisons, `and`, `or`, `not`, `implies`, no `in`; `metadata` and `@`, prefix metadata `#`; `doc` and `comment`;
  `alias … for
  …`; `public`, `private`, `protected`; `import X::*`; `standard library package`.
- The meaning of a redefinition (7.3.4.5): it "requires the values of the redefining feature and the redefined
  feature to be the same on each instance", so "any restrictions on the values of the redefining feature relative to
  the redefined feature, such as typing or multiplicity, also apply to the values of the redefined feature, and vice
  versa"; the redefined feature is "not inherited" but "replaced by the redefining feature". That is what a variant's
  `part LED5 …` means. A `default` value (7.4.11) applies "when an instance of the featuring type is constructed, if
  no other explicit values are given" – a block's parameter default.
- The libraries (Clause 9): the Kernel Semantic Library – Base, Links, Occurrences, Objects, Performances,
  Transfers, Clocks, Observation, Triggers, SpatialFrames, Metaobjects and the performance packages –, the Data
  Type Library and the Function Library for KerML; the Systems Library of SysML v2 (Parts,
  Ports, Connections, Interfaces, Items, Attributes, Constraints, Calculations, Requirements, Cases,
  VerificationCases, Metadata, …); the Domain Libraries (Quantities and Units with ISQ, SI and
  ISQElectromagnetism, Metadata, Geometry, Analysis, Cause and Effect, Requirement Derivation). KerML itself has
  nothing on units, requirements or variation; those are SysML v2's.
- **The mechanism for a domain inside SysML v2's syntax**: semantic metadata (7.4.13). A metaclass that
  specializes `Metaobjects::SemanticMetadata` names a `baseType`, and "each type annotated by such semantic metadata
  has an implicit specialization added" to it – a classifier subclassifies it, a feature subsets it. In SysML v2 that
  is the user-defined keyword: `#net` before a declaration. It is the way to add a domain such as circuits to SysML
  v2's own notation without changing the language; with a notation of edakit's own it is not needed, the library's
  types are specialized directly. The Systems Modeling Community names as its purpose to "provide support for
  building other modeling languages and domain-specific extensions based on KerML and/or SysML", and Seidewitz
  describes SysML v2 itself as such an extension of the kernel, with users defining domain-specific languages the
  same way.
- **What exists for electronics**: the quantities and units, nothing structural – no library of components, pins
  or nets, and none of the 22 example models is electrical. Circuits were a worked example in SysML v1's SysPhS,
  the extension for physical interaction and signal-flow simulation (version 1.1, May 2021, formal/21-05-03; "a
  platform-independent SysML library of simulation elements", translations to Modelica and Simulink/Simscape, an
  electric circuit as Annex A.2); a successor for SysML v2 was not found.

What that gives edakit: the meaning of redefinition, of inheritance down a variant chain, of multiplicity and of an
invariant from a standard instead of an invention; the export `edakit graph kerml` and `edakit graph sysml` as a
mapping, not a translation; a conformance test with a standard reader – the pilot implementation as a subprocess
with a JDK, Syster's `systree` once it leaves alpha, Syside Automator where a proprietary library is acceptable –
and the schema of clause 10 for the JSON export, checked from Python without a parser; a tool that imports the
export and draws it, Eclipse SysON; and the handbook's vocabulary. What it does not give: the electrical domain –
net, pin, role, LCSC number, board, order – which is edakit's library in any case and exists for SysML v2 nowhere
else; and nothing at run time, since the engines read the resolved graph.

Why KerML's own textual notation is not the source: it is more abstract than SysML v2's – `struct`, `feature`,
`connector` for `part def`, `part`, `connection` – at the same length, two to three times the notation of the
sketch; models have seen even less of it than of SysML v2, and the owner's measure is Sonnet; and a conforming KerML
reader with name resolution and implied relationships is many times the sketch's parser. The LED step in KerML, with
the grammar's forms:

```text
package Bell {
    import Electrical::*;                       // edakit's library: Block, Pin, Net, Resistor, LED
    struct LedStep :> Block {
        feature color : LedColor default green;  feature i : CurrentValue;
        feature in : Pin;  feature gnd : Pin;
        feature D : LED;
        feature R : Resistor { :>> value = seriesResistor(in.v, D.vf, i); }   // a function of edakit's library
        connector : Net (in, R.p1);  connector anode : Net (R.p2, D.anode);  connector : Net (D.cathode, gnd);
    }
    feature step1 : LedStep { :>> color = green;  feature :>> R { :>> designator = "R4"; :>> lcsc = "C17630"; } }
    connector : Net (u1.PD6, step1.in);
}
```

### Requirements on the same basis

The owner's rule reaches the requirements: if the circuit takes SysML v2's model, so do the needs and requirements
that `hardware/requirements.toml` holds today – `[[need]]` N- in someone's words, `[[requirement]]` R- as one
testable sentence with `from` (needs, decisions, a standard, a sign-off), `binding` must, should or may, `verify` as
rows of the gate protocol, a sign-off M-, a project script or an acceptance step, and a status draft, accepted or
dropped; DOCS.ref, DOCS.need, DOCS.evidence and DOCS.draft check it, the gate evaluates the evidence, the circuit
hash takes the file byte for byte ([requirements.md](../done/requirements.md); the file covers the circuit only, its
decision 3). SysML v2 has the model for exactly this, in its Systems Library and one domain library:

| edakit today | SysML v2 |
| --- | --- |
| `[[requirement]]` R-, one testable sentence | a `requirement` usage of a `requirement def`; the sentence its `doc` |
| what it is about – implicit today: the circuit, or the places a `rows` pattern names | `subject` – the Systems Library's `RequirementCheck` has `subject subj : Anything[1]` –: a net, a part, a usage |
| the condition – today the sentence, checked by the codes the pattern names | `require constraint { … }`, an expression over the subject's attributes; `assume constraint` for the operating condition |
| `from = ["N-1"]`, a requirement that follows from a need | the Requirement Derivation library: a `#derivation` connection with the ends `#original` and `#derive` – `original`, `derive` and `derivation` are its semantic metadata |
| `[[need]]` N-, `who` | a requirement at the top of a derivation chain, with the owner as `stakeholder` (`RequirementCheck` has `stakeholders : Part[0..*]`); a `concern` the requirements `frame` where a need is a wish without a check |
| `from = ["D-8"]`, a standard | `doc` and metadata, as for the graph's decisions |
| what satisfies it – nothing names it today | `satisfy requirement R3 by step1`: a usage, a part, a net of the circuit |
| `verify = [{ rows = "LIM.v *" }]`, `{ signoff = "M-1" }`, `{ script = "…" }`, `{ accept = "…" }` | a `verification case` whose `objective` names `verify requirement R3` and whose `return verdict : VerdictKind` – pass, fail, inconclusive, error – is the engine's finding, the human's sign-off, the script's exit or the acceptance step |
| `binding` must, should, may | an attribute of edakit's requirement def; SysML v2 has no binding of its own |
| `status` draft, accepted, dropped | an attribute of edakit's requirement def, as the gate reads it |

So the model is SysML v2's – requirement, subject, constraint, derivation, satisfy, verification case, verdict – and
the notation edakit's, as for the circuit:

```text
need N-1 "The countdown is visible across the room." who owner
requirement R-3 from N-1 must "Every countdown LED carries 2 to 15 mA while its step is on."
  subject led                                       # every usage of led; one requirement usage per subject
  require D.i within 2 mA .. 15 mA                  # the current through D, as the simulation measures it
  verify rows "LIM.i *"  verify rows "SIM.state *"
requirement R-7 from D-8 should "A USB power bank stays on: the circuit draws at least 100 mA."
  subject +5V
  verify signoff M-1
```

What that changes against today: a requirement names its subject, so DOCS.ref resolves one more kind of reference
and `graph show` lists the requirements on a net or part; a requirement with a `require` states its condition as
SysML v2 does and is checked by what its `verify` names – the simulation's criteria, the bell's `led_on_min_a` in
`sim.json`, the entries' limits through LIM.i, a sign-off –, not by an evaluator of the notation's own (item 4); the
compiler checks that a `require` has its `verify`, as DOCS.evidence does today; `satisfies R-3` on a usage (the
fifth value above) is `satisfy` from the other end; the derivation from a need to a requirement is a relation with
a standard's name instead of a list. What stays edakit's: the codes as evidence, the sign-offs with their hash, the
acceptance test on the built board, draft and accepted, the file covering the circuit only. The form: the same
notation, in `hardware/requirements.circuit` or in the circuit's files, compiled to the resolved requirements that
`edakit req`, the DOCS codes and the gate read today – TOML stays the flat form here too –, and exported with
`edakit graph sysml` as requirement usages with `satisfy` and `verify`, so that a SysML tool
shows which part satisfies which requirement and how it is verified. Regulatory requirements stay what the gate
protocol says of them: support, not legal advice.

`.ato` is the right model for the syntax – units with tolerances, derived values, arrays, chains – and the wrong
basis: adopting the syntax without the compiler is a reimplementation of a syntax that was itself rewritten in 2026,
adopting the compiler binds edakit to a picker-centric, KiCad-only tool chain on Python 3.14 whose documentation and
workspace have moved into a browser editor behind a sign-in. A notation modeled on it, not compatible with it.

Python is the fallback, not the basis: if the evals show that a model edits the notation worse than a program, a
restricted Python API with the resolved graph as the artifact is the way with the least syntax. The price is that only
a model can edit the source.

The recommendation: a notation of edakit's own, small, declarative, defined by the owner's rule – on SysML v2's
Systems Library where its terms fit, part, port, connection, attribute, requirement, variation, constraint; on
KerML's kernel where they do not; every construct an element of an electrical library on that basis –, with `.ato`'s
ergonomics, compiled to the resolved graph and exportable to SysML v2 and KerML; TOML with names stays the flat form.
The sketch's reader is the measure – 231 lines of `translate.py`, the whole prototype with writer, TOML and round
trip 819 –: definitions, usages, `for`, derivations and variants are each a construct of the reader's
size, and the compiler to the resolved graph is the sketch's writer. What has to be built is the section "The
toolchain" below.

## When it brings value

Not before, and not without, these:

1. **The TOML form is built** ([circuit-language-plan.md](circuit-language-plan.md), L.1 to L.9): pins by name or
   role, the resolved `graph.json` beside the form, `--check` in the hook. The language compiles to the same
   artifact; without it, it has no target.
2. **Blocks want parameters.** Measured in the projects: three or more blocks whose values a project changes – the
   LED current, a pull-up, a divider – and the notes "another value of the same series" in the graph.
3. **A project with repetition or variants is at hand.** The bell's four configurations are one today (the section
   above); the tree's move to edakit (30 LEDs on three drivers) and the pedal's second module would be two more.
4. **The shape of the graph stands still.** The cut `4982d35` of 2026-10-31 changed shapes – `waive` to `accept`,
   `hints` to HINT codes, `checks.pin_locks` to `locks.pins` –, and the same day added keys: `config`, `states`,
   `strip`, `isolated`, `clock_hz`, `accept` by place. Since the cut the graph gains keys only; whether the shape –
   components, nets, cables, layout, locks, accept, purpose – still stands is judged when the decision is due, with
   no waiting period (the owner, 2026-10-31). The language itself adds one key, `derivations` (item 4 above).
5. **Evidence.** `evals/add-led`, a repetition task and a variant task on the reference circuits, in TOML and in the
   language, three runs each with Sonnet (maker-coverage FT-24): the language at least as reliably edited.
6. **A budget of size L** for the first stage, and the readiness to maintain a construct, not a key, per change.

Whether and when to build it is the owner's decision, due when the triggers hold; then stage 1 first, so that the
value is measured before the cost is paid. The alternatives: a prototype now on the bell and led-bar, as the sketch
was – a decision on evidence sooner, but a prototype that waits for the TOML form to have a target –; or not at all,
which is TOML with names, `block add` with parameters as flags and `graph show` for slices.

The stages, each useful on its own:

- **Stage 1: edakit's block library in the language.** The 26 blocks as definitions with parameters, compiled to
  the block JSON `block add` reads today; `block add --set i=10mA` passes a parameter: the block's derivation runs
  with the entries, the command prints the derived value and the nearest value of the series and asks – it never
  writes a value no entry has, the designer chooses – and writes the record into the graph. Projects change
  nothing; the compiler, the quantities and the derivation rules are built and tested on edakit's own data. Size L.
  A project first would show the value earlier and build the compiler on one project's needs.
- **Stage 2: projects.** `hardware/graph.circuit` beside or instead of `graph.toml`, with `use`, `for`, variants and
  derivations; `edakit graph json` compiles either; `edakit graph show` (built 2026-10-31, FT-23) reads the resolved
  graph as it reads `graph.json` today and changes nothing. The bell and the tree as the first users, each at the
  user's request. Size M to L.
- **Stage 3: the exports.** `edakit graph sysml`, the model SysML tools draw and whose requirements and variants
  they follow, and `edakit graph kerml`, the kernel view as the interchange JSON of clause 10.4 – both a mapping,
  since the notation is defined on the libraries –; the electrical library on SysML v2 that the mapping targets,
  `Pin`, `Net`, `Resistor`, `LED`, `Block`, a requirement def with binding and status, metadata for `accept`, locks
  and decisions, written once and the one artifact of the export others could import; the conformance test as an
  optional job – the pilot implementation's reader as a subprocess with a JDK, or `systree` once it leaves alpha –
  and the schema check of the JSON export in Python; the acceptance test an import into Eclipse SysON, done by hand
  and documented. The requirements go with it, as requirement usages with `satisfy` and `verify`. Not built: a
  SysML v2 reader of edakit's own – that is the pilot's, Syster's and Sensmetry's work. Never exporting would save
  the mapping and give up the interoperability and the conformance test; the standard's notation as the source is
  weighed in "The basis".
- **Stage 4: a language server and a VS Code extension.** For the human in the editor: the reader's errors as they
  are typed, go to definition – a pin word to its entry, a usage to its definition, a net to its pins –, hover with
  the entry's limits and the net's range, completion of pin words, designators and codes, all over the reader and
  resolver the CLI uses; the extension brings the grammar of stage 1, the server's client, the formatter on save,
  `graph json --write` and `--check` as tasks, `graph show` for the element under the cursor, and the findings of
  `edakit check` at the statements they come from, through a source map the compiler writes beside the resolved
  graph – a net's LIM.v at its `net` line, a derivation's DEF.derive at its `derive`. The model needs none of it –
  it edits through the CLI and `graph show` –, so it comes last. Size M for the server, M for the extension.

The value, estimated on the owner's projects: the bell's main file from 59 statements in the sketch's language (the
translator's output; the hand-written `bell.circuit` has 72 lines of content) to about 50 – the bell has little
repetition, its gain is the variants –; led-bar's eight LEDs from 244 lines of JSON to four; the graph of the tree
(pytree, the reference project, 65 KB), which no session should read whole, to a size a session can read; the bell's
four configurations to one main file and three variant files of about a dozen, a dozen and twenty lines against 69,
64 and 83 statements today, with sign-offs that survive a change of the main file where it does not reach them.

## The toolchain

What the language needs beside edakit as it is, with what exists today and the stage that builds it. Sizes as in the
plans: S a day, M a few days, L a week or more.

| Piece | What it does | Exists today | Size | Stage |
| --- | --- | --- | --- | --- |
| Reader | the statements with their lines – `graph`, `part`, `net`, `cable`, `layout`, `accept`, `description`, `purpose`, `include`, `param`, `def`, `use`, `for`, `derive`, `variant`, `alias`, `need`, `requirement`, `satisfy`, `verify` –, every error with file and line, shapes checked before any check runs | the prototype's `Reader`, 231 lines, for the sketch's statements in the old form | M | 1 |
| Resolver and compiler | names resolved across files – `include`d files, a variant chain in order, definitions from the project's files and then edakit's library, requirements files – into one namespace per project; usages and loops expanded, redefinitions applied, pin words to numbers through the entries (L.1, L.2), the derivation records and the resolved requirements written, a stable order: a function from files to the resolved graph | the prototype's writer to JSON; L.5's `edakit graph json` for TOML, once built | L | 1 for definitions, 2 for projects |
| Quantities and derivation rules | quantities with units, ranges and tolerances as the inputs; `series_resistor`, `divider`, `pullup`, `rc` … as functions with their corners, units and series, evaluated by the compiler into the records; free expressions with the units checked only when a project needs them (item 4) | `QUANTITY` and `MULTIPLIERS` in circuit.py for `330Ω`, `4k7`, `100nF`; `v_range` for nets; `UNITS` in engines/quantities.py; the simulation's LED model and LIM.i know the corners | M | 1 |
| Engine DEF | `DEF.derive` from the graph's `derivations`: a part's value against its record's derived value and series, numbers only, with the catalog's severities and the domains' grades | the engines' frame, the catalog's code table, STRUCT.identity as the pattern | S | 1 |
| `edakit graph json` for `.circuit` | `--write` the resolved graph, `--check` the drift, per project; the pre-commit hook of L.5 runs it | `edakit graph show`; `edakit firmware --check` as the pattern; the bell has no hook today | S on L.5 | 2 |
| `edakit graph fmt` | the canonical layout, comments kept, so that a diff shows data | the prototype's writer, which lays out but keeps no comments | S to M | 1 |
| `edakit graph convert --to circuit` | a JSON or TOML graph as flat statements – no usages: those come from `block add` or by hand | the prototype's writer | S | 2 |
| `block add` on the language | writes a usage with its bindings and designators, `--set` for parameters, `--without` for optional parts | `block add` on JSON, `plan()` in block.py, `--without` | M | 1 for `--set`, 2 for usages |
| The library as definitions | the 26 blocks with parameters and derivations, compiled to the block JSON of today | `edakit/blocks/*.json` | M | 1 |
| Editor grammar | a TextMate grammar for VS Code and a Pygments lexer for the documentation site; GitHub highlights no language of one's own, a `.gitattributes` mapping lends another language's colours at best | – | S | 1 |
| Tests and evals | reader and compiler tests; golden files source → resolved graph for the bell's four files and led-bar; the round trip compile → convert → compile; determinism, two runs identical; `evals/add-led`, a repetition task and a variant task in the language, three runs each with Sonnet (FT-24) | `evals/add-led` in JSON; the prototype's round trip | M | 1 and 2 |
| Handbook, reference, skills | a chapter on the language, the reference of statements, the skills circuit-design and hardware-change that write it, the README | the chapters of the TOML form (L.8), once written | M | 1 and 2 |
| Exports | `edakit graph sysml` and `edakit graph kerml` from the resolved graph, the source's definitions and the requirements; the electrical library on SysML v2 they target; the schema check of the JSON export; the conformance test with the pilot's reader as an optional job | – ; the pilot implementation (Java, installers in the release repository), Eclipse SysON for the import, `systree` in alpha, `syside` proprietary | M | 3 |
| Language server | diagnostics as typed, go to definition, hover, completion, over the reader and resolver | – ; `pygls` as the frame in Python | M | 4 |
| VS Code extension | the grammar, the server's client, format on save, `graph json --write` and `--check` as tasks, `graph show` for the element under the cursor, the findings of `edakit check` at their statements through the compiler's source map | – ; the source map is a small addition to the compiler | M | 4 |

Not built: free expressions before a project needs them (item 4), part picking, any I/O from the language, a SysML
v2 reader of edakit's own – the pilot's, Syster's and Sensmetry's work –, clients for editors other than VS Code –
the grammar and the server serve any editor, the client is written once. Stage 1 is the reader, the compiler for
definitions, the quantities and the derivation rules, DEF, the formatter, the grammar, the library, the chapter and
the tests: size L, as
said. Stage 2 adds the project constructs – `use`, `for`, variants, `alias`, `param`, `include`, the requirements
statements –, `graph json` and the hook for `.circuit`, the converter, `block add` writing usages, the skills and the
evals: M to L. Stage 3 the exports: M. Stage 4 the language server and the extension: M and M.

## Costs and risks

- **A second front-end.** TOML and the language both end in the resolved graph; every tool that writes the graph
  writes both or writes the resolved graph only. Cut: `block add` writes a usage in the language and a table in
  TOML; everything else reads the resolved graph. A project has one source form, named by `[project] graph`.
- **A program in disguise.** Derivations, `for` and variants are where a notation turns into a language nobody can
  review. Guardrails: named rules instead of free expressions (item 4), no conditionals, no loops but ranges, no
  I/O, and the resolved graph as what the reviewers and the diff read.
- **The library binds projects.** A definition in edakit changes, the resolved graphs of the projects that use it
  change – visible through `--check` in each project, never silently. A project may pin a definition by copying it
  into its own file.
- **A base reaches its variants.** A change of the bell's main file changes three resolved graphs in three projects;
  without one step that regenerates and one hook that checks all four, a variant's committed graph drifts unnoticed
  (the bell's model above).
- **Models.** A notation nobody has seen is learned from the handbook; the evals decide whether that holds for Sonnet.
  The fallback is Python.
- **Size.** Stage 1 is size L: parser, compiler, quantities with units, the derivation rules, the engine DEF, a
  formatter, a grammar, handbook chapter and tests. Stage 2 adds `use`, `for`, variants, the project commands and
  the skills.
- **The regulatory review** reads the resolved graph's `purpose` as today; nothing of it moves into a definition. It
  stays support, not legal advice.

## Sources

Read on 2026-10-31 from this session:

- atopile: [the repository](https://github.com/atopile/atopile) (README, `pyproject.toml`,
  `examples/auto-picking/auto-picking.ato`,
  [releases](https://github.com/atopile/atopile/releases), [tags](https://github.com/atopile/atopile/tags),
  [discussions](https://github.com/atopile/atopile/discussions)); the issues
  [#1821](https://github.com/atopile/atopile/issues/1821) and [#1827](https://github.com/atopile/atopile/issues/1827)
  with the contributor's statement on app.atopile.io; the third-party issue
  [Marwichmisi/NIA-PCB#3](https://github.com/Marwichmisi/NIA-PCB/issues/3) quoting the CLI message;
  [docs.atopile.io](https://docs.atopile.io) (the landing page with the new syntax and "the docs live in the editor
  now") and the [blog feed](https://atopile.io/blog/feed.xml) (0.16.15), read through the session's proxy; the
  language reference itself sits inside the editor behind the sign-in and was not read;
  [PyPI's JSON API](https://pypi.org/pypi/atopile/json) for the releases, their licence and their source
  distributions (the project page itself answered with a challenge page); the
  [source distribution of 0.15.9](https://files.pythonhosted.org/packages/ec/70/7611a5fae81aab1f90ad071abd0861d6081606cfbd234ded5b8734dd94ff/atopile-0.15.9.tar.gz)
  (SHA-256 `681cc1e1…`), read, not run: `AtoParser.g4` and `AtoLexer.g4`, `examples/*.ato`, `src/faebryk/library`,
  `src/faebryk/libs/app/erc.py`, `src/atopile/build_steps.py`, `src/atopile/config.py`, `src/atopile/cli/motd.py`.
- faebryk: [the repository](https://github.com/atopile/faebryk) (README, releases, `examples/minimal_led.py`).
- SKiDL: [PyPI 3.0.0](https://pypi.org/project/skidl/3.0.0/). PCBDL: [the repository](https://github.com/google/pcbdl).
  codeyourpcb: [the repository](https://github.com/szymontex/codeyourpcb) and its
  [SYNTAX.md](https://github.com/szymontex/codeyourpcb/blob/main/docs/SYNTAX.md). tscircuit:
  [tsci export](https://docs.tscircuit.com/command-line/tsci-export). Not reachable: circuit-synth's documentation,
  JITX's site, the PHDL paper at OSTI.
- KerML: [About KerML 1.0](https://www.omg.org/spec/KerML/1.0/About-KerML) and the
  [specification](https://www.omg.org/spec/KerML/1.0/PDF) (formal/26-03-01; Clauses 1, 2, 6.1, 7.3.4.5, 7.4.4,
  7.4.6, 7.4.8.5, 7.4.11, 7.4.13, 9, 10 read), [About SysML 2.0](https://www.omg.org/spec/SysML/2.0/About-SysML)
  (formal/26-03-02 and 26-03-03) and [About SysPhS 1.1](https://www.omg.org/spec/SysPhS/1.1/About-SysPhS), read
  through the session's proxy once the owner had allowed the host; from the OMG's release repository on GitHub the
  [KerML textual grammar](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/bnf/KerML-textual-bnf.kebnf),
  [Metaobjects.kerml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml.library/Kernel%20Libraries/Kernel%20Semantic%20Library/Metaobjects.kerml)
  (`SemanticMetadata`), the [Kernel Libraries](https://github.com/Systems-Modeling/SysML-v2-Release/tree/master/sysml.library/Kernel%20Libraries),
  the [Systems Library](https://github.com/Systems-Modeling/SysML-v2-Release/tree/master/sysml.library/Systems%20Library),
  the [Domain Libraries](https://github.com/Systems-Modeling/SysML-v2-Release/tree/master/sysml.library/Domain%20Libraries)
  with [ISQElectromagnetism.sysml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml.library/Domain%20Libraries/Quantities%20and%20Units/ISQElectromagnetism.sysml),
  the [KerML examples](https://github.com/Systems-Modeling/SysML-v2-Release/tree/master/kerml/src/examples); the
  README's statement of the Systems Modeling Community's purpose; Seidewitz,
  [On a Metasemantic Protocol for Modeling Language Extension](https://www.scitepress.org/Papers/2020/91816/91816.pdf)
  (2020).
- SysML v2: [the release repository](https://github.com/Systems-Modeling/SysML-v2-Release) with the
  [textual grammar](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/bnf/SysML-textual-bnf.kebnf),
  the [variability
example](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml/src/examples/Variability%20Examples/VehicleVariabilityModel.sysml)
  and the [vehicle example of Annex
A](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml/src/examples/Vehicle%20Example/SysML%20v2%20Spec%20Annex%20A%20SimpleVehicleModel.sysml)
  (`satisfy … by`, `verify`, `60 [kg]`); the OMG's
  [adoption announcement](https://www.omg.org/news/releases/pr2025/07-21-25.htm);
  [Syster](https://github.com/jade-codes/syster) and its Python wrapper on
  [PyPI, `systree`](https://pypi.org/pypi/systree/json) (0.4.4a0, February 2026, MIT); the
  [resource list](https://github.com/daltskin/SysML-v2-Resources) naming Syside Automator and the ANTLR grammars;
  on the owner's question the same day the tools on GitHub: the
  [release repository's README](https://github.com/Systems-Modeling/SysML-v2-Release) (the installers of the pilot
  implementation, Eclipse plugins and a Jupyter kernel; the pilot's own README was not reachable),
  [Eclipse SysON](https://github.com/eclipse-syson/syson) (README, EPL 2.0) and its
  [changelog](https://github.com/eclipse-syson/syson/blob/main/CHANGELOG.adoc) (textual import and export),
  Sensmetry's [sysml-2ls README](https://github.com/sensmetry/sysml-2ls) (the retired language server, the Syside
  suite: Editor free, Modeler and Automator commercial), [PyPI, `syside`](https://pypi.org/pypi/syside/json)
  (1.0.0b1, October 2026, proprietary); Sensmetry's announcement of the licence change was not reachable through
  the proxy; on 2026-10-31 also the library files
  [Requirements.sysml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml.library/Systems%20Library/Requirements.sysml)
  (`RequirementCheck` with `subject`, `actors`, `stakeholders`),
  [VerificationCases.sysml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml.library/Systems%20Library/VerificationCases.sysml)
  (`verdict`, `VerdictKind`, `PassIf`) and
  [RequirementDerivation.sysml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml.library/Domain%20Libraries/Requirement%20Derivation/RequirementDerivation.sysml)
  (`original`, `derive`, `derivation` as semantic metadata). The OMG pages and atopile's site resolve through the
  session's proxy only; the fetch tool of the background agents does not use it.
- The Christmas bell at `059162a`, read-only: `docs/decisions.md` (D-11 to D-17), `variants/README.md`, the four
  `edakit.toml`, `hardware/graph.json`, `sim.json` and `signoff.json` of main and the variants, `src/firmware`,
  `variants/esp32/firmware`; the prototype's round trip run on all four configurations.
- edakit at `bd227e3`: handbook 3, 4 and 14.5 (the blocks), `edakit/blocks/*.json`, `block.py`, `circuit.py`
  (`QUANTITY`), `engines/quantities.py`, `release/gate.py` (`state_hash`), `config.py` (`[project] requirements`),
  `catalog/codes.toml` (DOCS.ref, the HINT codes), `tests/fixtures/led-bar`, `tests/reference.py`, `evals/`, the
  prototype [translate.py and bell.circuit](../done/prototypes/circuit-language/),
  [maker-coverage.md](../done/maker-coverage.md) (the owner's projects, FT-23, FT-24, the stability of the model),
  [circuit-language.md](../done/circuit-language.md) (the sketch, its review and decisions) and
  [circuit-language-plan.md](circuit-language-plan.md).
