# A language of its own for the circuit: what it would have to be, on which basis, and when

Status 2026-10-31: concept, asked for by the owner after the review of [circuit-language.md](circuit-language.md)
deferred the language of that sketch. It answers four questions: whether a fitting language exists already, what a
language of edakit's own would have to be able to do to be worth building, on which basis – SysML v2, KerML, an
existing circuit language, or something else –, and when it would bring value. Nothing is decided; the decisions at
the end are open, the recommended answer first. The survey was made from this session, in which several sites were
not reachable; the sources say what was read and what was not. Against the yardstick: a language changes nothing
about what is text – its source and its resolved graph are text in the repository –; what it changes is where
repetition, parameters and variants are written once instead of many times.

## The short answer

No existing language fits as edakit's source. The ones that have the right shape are bound to their own compilers:
atopile's `.ato` has modules, units with tolerances, assertions and arrays, but its nets are implicit, its parts come
from a picker instead of a parts entry with roles and limits, it targets KiCad only, and its open future is
uncertain. SysML v2 has the right semantics for the layer above the circuit – definitions and usages, redefinition,
variation, requirements with satisfy and verify, units –, but no electrical semantics at all, a verbose notation and
open tooling in its infancy. The Python libraries (SKiDL, PCBDL, faebryk, circuit-synth) make the circuit a program,
which edakit's tools cannot edit. The rest is proprietary, dormant or one person's experiment.

What is worth taking: SysML v2's semantics as the model behind the language, so that its vocabulary is a standard's
and an export to SysML v2 is possible; `.ato`'s ergonomics as the model for the syntax – units with tolerances,
`assert … within`, arrays, chains –; and edakit's own resolved graph (decision 4 of circuit-language.md) as the compile
target, so that every check, the hash and the reviews keep reading what they read today.

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
   eight pins in `+5V`. In led-bar that is about 150 lines of JSON; in the tree 30 LEDs on three drivers.
3. **Parameters, derived values and constraints.** A block's values are fixed today – 150 Ω in `led`, "another
   current: another value of the same series" in its notes. With a parameter the definition says what the value
   depends on, `(in.v.max − D.vf) / i`, and an assertion holds the part that was chosen to it. The derivation becomes
   text that a reviewer reads, instead of a number Claude computed in its head and a check verified afterwards.
4. **Variants as differences.** The bell's four configurations differ in parts and texts; a variant that names the
   main file and redefines what differs is a few lines. With the resolved graph as the hashed artifact (below), a
   change of the main file voids a variant's sign-offs only when it changes the variant's resolved circuit – the
   objection of circuit-language.md against `use` falls away.

A fifth, smaller: a usage can name the requirement it satisfies and the decision it follows, `satisfies R-3`,
`decision D-8`, resolvable by DOCS.ref instead of free text in `notes`.

What a flat form keeps: everything else. TOML with names (decided 2026-10-31) is the flat, explicit form; a language is
the composed, parametric one. Both end in the same resolved graph, so a project can start flat and move when its
repetition grows.

## What exists

Read from this session on 2026-10-31; the sources at the end say what was reachable.

| Language | Kind | What it has that edakit would want | What it lacks or what binds it | State |
| --- | --- | --- | --- | --- |
| atopile `.ato` | declarative language with its compiler | modules, `new`, arrays `new LED[2]`, units with tolerances `10kohm +/- 20%`, `assert … within`, `~` and `~>` chains, `for` (behind a pragma), `lcsc_id`, package constraints, parametric part picking, an ERC | nets are implicit in connections and carry no attributes (`v`, `fn`, `accept`); parts come from a picker, not from an entry with roles, limits and sources; KiCad only; no simulation; Python 3.14 only, a native Zig core since 0.14, an ANTLR parser; the compiler is the language | MIT. The public repository's last tag is from February 2026; 0.15.x is on PyPI by users' reports; a contributor wrote in August 2026 that native Windows support is replaced by app.atopile.io from 0.16 on; a third party quotes a CLI message that 0.15.8 is the last CLI release – not confirmed by atopile in what was reachable |
| faebryk | Python library, atopile's former core | modules as classes, interfaces, `connect`, parameters by `merge`, a picker | a program, not data; a C++ core; Python 3.12 only | archived December 2024, merged into atopile |
| SKiDL | Python library | parts, nets, hierarchical subcircuits, ERC, netlists for KiCad 5–10 and SPICE; models know Python | a program; no units, no constraints beyond ERC, no net attributes; KiCad symbols as the part model | 3.0.0 in October 2026; one maintainer since 2016 |
| PCBDL | Python library (Google) | parts and nets with `<<`, a schematic as SVG | no hierarchy, no ERC, an Allegro netlist | Apache 2.0; archived January 2023 |
| circuit-synth | Python with a JSON in the middle, KiCad | an interchange JSON "any tool can read and write" | not reachable from here; nothing more is known | unverified |
| tscircuit | TypeScript and React (JSX) | components as JSX, a circuit JSON, DSN export, SPICE, written for coding agents | a TypeScript stack; a program; a React tree as the model | MIT, active |
| JITX | commercial language | bundles, design rules, constraint-driven routing | proprietary | not reachable from here |
| codeyourpcb | a DSL of its own | `component`, `net VCC [width 0.5mm] { J1.1; U1.8 }`, `module` and `use Divider as SENSE { IN = VIN }`, imports, DRC, Gerber | no parameters; "the DSL and file format may change between versions"; no parts data model | MIT or Apache 2.0; October 2026, one author |
| PHDL | an HDL for boards (Brigham Young University, a DOE paper) | design, device, instance, net, arrays, attributes, hierarchy | dormant since about 2014, Java; the paper was not reachable from here | historical |
| SysML v2 with KerML | OMG standard, textual notation | `part def` and `part`, `port def`, n-ary `connection : Net connect (a.p, b.p, c.p)`, redefinition `:>>`, `variation` with `variant` and a selection by redefinition, `requirement`, `satisfy … by …`, `verify`, `constraint def`, `calc def`, units `60 [kg]` | no electrical semantics: no net, pin, part data, board, order; verbose; open tooling: the pilot implementation in Java and Xtext, Syster in Rust (MIT, alpha, no release), ANTLR grammars; models have seen little of it | 2.0 adopted by the OMG in 2025, KerML 1.0 with it, an editorial update for ISO in March 2026 |
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
semantics; `.ato`'s units, tolerances, assertions and arrays for the syntax.

**KerML** is the kernel SysML v2 is built on – classifiers, features, types, expressions, specialization,
redefinition, multiplicity –; nobody writes it directly. It is useful as the reference for what a definition, a usage
and a redefinition mean, and for nothing else here.

## What it would have to be able to do

1. **Definitions and usages.** A definition has ports, parameters with defaults, internal parts and nets, `covers`,
   `optional` parts and notes – today's block JSON, written in the language. edakit's library and a project's own. A
   usage names the definition, binds its ports to nets, sets parameters, and names the designators and parts entries
   of the internal parts, so that the BOM and the board see what they see today.
2. **Pins by name or role, nets first-class.** As decided for the shared part: `U1.PD6`, `LED5.anode`, a net with
   its attributes, n-ary. Internal nets of a usage are named `<instance>_<net>` as `block add` names them, unless the
   usage names them.
3. **Repetition.** `for n in 0..7` over parts and nets with `{n}` in names and pin words – ranges and index
   arithmetic, nothing more.
4. **Parameters with units, expressions and assertions.** Quantities as edakit reads them already (`330Ω`, `4k7`,
   `100nF`, `0..5.5 V`), with tolerances and ranges (`10 mA ± 20 %`, `2 mA .. 15 mA`); arithmetic on them with the
   units checked; `assert <expression> within <range>` evaluated when the graph is compiled. A failed assertion is a
   finding of a new engine, `DEF.assert`, with the severity the profile gives it; an unbound port `DEF.port`, a
   parameter outside its range `DEF.param`. No part picking: the designer chooses the part, the assertion and
   STRUCT.identity hold it to the derived value.
5. **Variants as differences.** A variant file names the main file and redefines parts, values and texts by
   designator and name; everything else is inherited. Its resolved graph is complete and is what the hash and the
   sign-offs bind to.
6. **References.** `satisfies R-3`, `decision D-8` as attributes DOCS.ref resolves.
7. **Attributes pass through.** Every key of the graph's schema is written as `key value` on a part, a net or the
   graph and reaches the resolved graph unchanged. The language has syntax only for composition; a new key of the
   schema never needs a syntax decision. What has to stand still is the shape of the graph – components, nets,
   cables, layout, locks, accept, purpose –, not its keys.
8. **Determinism and a resolved graph.** The compiler is a function from the sources to the resolved graph of today's
   format, with pin numbers and the full pin maps, in a stable order; no input but the files, no output but the
   graph. `edakit graph json --write` writes it, `--check` in the pre-commit hook reports drift, as decided for the
   TOML form. A project's committed resolved graph pins its circuit against a change of edakit's block library: the
   library may move, the check says so, the user decides.
9. **Designators explicit.** A usage names the designators of its parts; the tool that writes a usage (`block add`)
   allocates them once, as it does today. Nothing is renumbered by the compiler.
10. **Errors with file and line, a formatter, a grammar for highlighting.** Preconditions, not costs: the sketch's
    parser found every error with its line; the rest is a day each.

Not in it: behavior (SPICE models stay in the parts entries), layout (stays in the board files; a definition may carry
layout intent for its instance – `near`, loops – as the hand-over does), part picking, conditionals, loops beyond
ranges, any I/O.

## How it could look

The sketch's statements, extended by definitions, usages, repetition, assertions and variants. The bell's LED step as
a definition, with the current as a parameter:

```text
def led (color = green, i = 2 mA .. 15 mA) ports in gnd
  part R resistor
  part D led value color
  net in     R.1
  net anode  R.2 D.anode    v @in
  net gnd    D.cathode
  assert (in.v.max - D.vf.min) / R.value within i     "the current at the top of the input's range"
  covers LIM.v LIM.i LVL.threshold SIM.state
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

Repetition, led-bar's eight LEDs on the driver's outputs – today 8 parts, 8 nets and 8 pins in `+5V`, about 150
lines of JSON:

```text
for n in 0..7
  part D{n+2} led KT-0805G lcsc C2297 value green "LED {n+1} (green 0805)"
  net LED{n} 0..5.5 V U2.OUT{n} D{n+2}.cathode
  net +5V D{n+2}.anode
```

A variant, the bell's SMD configuration – today a complete graph of its own:

```text
variant smd of ../../hardware/graph.circuit
  use led step1 D = LED5 lcsc C2286 part KT-0805G     # the 0805 LED, anode on pin 1; everything else inherited
  …
  set description "… the SMD configuration"
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
| a need or requirement N-, R- | `requirement def` and usage, `satisfy … by …` |
| a gate row, a sign-off M- | a verification case, `verify` |
| a decision D- | documentation (`doc`); no relationship of the standard |
| `accept`, the hash, the release | nothing |
| a quantity with its unit | ISQ and SI, `10 [mA]` |

So: the model yes, the notation no. The notation is two to three times the text for a 19-part circuit, every
connection in the examples is binary and a net would be a construction of edakit's own, the electrical layer and the
manufacturing data would be attributes without meaning to any SysML tool, the open parsers are a Java pilot
implementation and an alpha in Rust, and models have seen little SysML v2. What the model gives: a vocabulary that is
a standard's – definition, usage, redefinition, variation, satisfy, verify –, clean rules for what a redefinition
means, and the option of an export `edakit graph sysml` for whoever models the system around the board in SysML v2.

`.ato` is the right model for the syntax – units with tolerances, `assert … within`, arrays, chains, `lcsc_id` – and
the wrong basis: adopting the syntax without the compiler is a reimplementation, adopting the compiler binds edakit
to a picker-centric, KiCad-only tool chain on Python 3.14 whose open branch may be frozen. A notation modeled on it,
not compatible with it.

Python is the fallback, not the basis: if the evals show that a model edits the notation worse than a program, a
restricted Python API with the resolved graph as the artifact is the way with the least syntax. The price is that only
a model can edit the source.

The recommendation: a notation of edakit's own, small, declarative, with SysML v2's semantics and `.ato`'s
ergonomics, compiled to the resolved graph; TOML with names stays the flat form; a SysML v2 export later, if anyone
asks for it. The sketch's parser (242 lines) is the measure: definitions, usages, `for`, expressions, assertions and
variants are each a construct of that size, and the compiler to the resolved graph is the sketch's writer.

## When it brings value

Not before, and not without, these:

1. **The TOML form is built** ([circuit-language-plan.md](circuit-language-plan.md), L.1 to L.9): pins by name or
   role, the resolved `graph.json` beside the form, `--check` in the hook. The language compiles to the same
   artifact; without it, it has no target.
2. **Blocks want parameters.** Measured in the projects: three or more blocks whose values a project changes – the
   LED current, a pull-up, a divider – and the notes "another value of the same series" in the graph.
3. **A project with repetition or variants is at hand.** The tree's move to edakit (30 LEDs on three drivers), the
   pedal's second module, the bell's four configurations.
4. **The shape of the graph stands still.** Since `75d5c32` the graph gained keys, not shapes; the shape – components,
   nets, cables, layout, locks, accept, purpose – has stood since the cut. Two months without a change of shape.
5. **Evidence.** `evals/add-led`, a repetition task and a variant task on the reference circuits, in TOML and in the
   language, three runs each with Sonnet (maker-coverage FT-24): the language at least as reliably edited.
6. **A budget of size L** for the first stage, and the readiness to maintain a construct, not a key, per change.

The stages, each useful on its own:

- **Stage 1: edakit's block library in the language.** The 26 blocks as definitions with parameters, compiled to
  the block JSON `block add` reads today; `block add --set i=10mA` passes a parameter. Projects change nothing; the
  compiler, the expressions and the assertions are built and tested on edakit's own data. Size L.
- **Stage 2: projects.** `hardware/graph.circuit` beside or instead of `graph.toml`, with `use`, `for`, variants and
  assertions; `edakit graph json` compiles either; `graph show` reads a slice of the resolved graph (FT-23). The bell
  and the tree as the first users, each at the user's request. Size M to L.
- **Stage 3, optional: a SysML v2 export** of the resolved graph with its definitions – an afternoon, when someone
  models the system around the board.

The value, estimated on the owner's projects: the bell from 72 lines of content in the sketch's language to about 30;
led-bar's eight LEDs from about 150 lines of JSON to three; the tree's 65 KB graph, which no session should read
whole, to a size a session can read; the bell's four configurations to one main file and three variant files of a
few lines each, with sign-offs that survive a change of the main file where it does not reach them.

## Costs and risks

- **A second front-end.** TOML and the language both end in the resolved graph; every tool that writes the graph
  writes both or writes the resolved graph only. Cut: `block add` writes a usage in the language and a table in
  TOML; everything else reads the resolved graph. A project has one source form, named by `[project] graph`.
- **A program in disguise.** Expressions, `for` and variants are where a notation turns into a language nobody can
  review. Guardrails: no conditionals, no loops but ranges, no I/O, expressions only on quantities, and the resolved
  graph as what the reviewers and the diff read.
- **The library binds projects.** A definition in edakit changes, the resolved graphs of the projects that use it
  change – visible through `--check` in each project, never silently. A project may pin a definition by copying it
  into its own file.
- **Models.** A notation nobody has seen is learned from the handbook; the evals decide whether that holds for Sonnet.
  The fallback is Python.
- **Size.** Stage 1 is size L: parser, compiler, expressions with units, assertions, the engine DEF, a formatter, a
  grammar, handbook chapter and tests. Stage 2 adds `use`, `for`, variants, the project commands and the skills.
- **The regulatory review** reads the resolved graph's `purpose` as today; nothing of it moves into a definition. It
  stays support, not legal advice.

## Open decisions

Each a real choice, the recommended answer first, with its trade-off; none is due before the triggers above hold.

1. **The basis.**
   - *A notation of edakit's own with SysML v2's semantics and `.ato`'s ergonomics, compiled to the resolved graph*
     (recommended): fits the data, stays small, tools can edit it; a parser and a chapter to build, a syntax to learn.
   - *SysML v2's textual notation with an electrical library*: a standard, requirements and variants built in; two to
     three times the text, no electrical semantics, alpha tooling, a notation models barely know.
   - *A subset compatible with `.ato`*: some familiarity and an editor extension for free; edakit's nets, entries and
     keys are not `.ato`, so the files would not be valid `.ato` anyway, and the compatibility binds to a moving target.
   - *A restricted Python API*: no syntax to invent, the form models write best; a program as the source that only a
     model can edit.
2. **The first use.**
   - *edakit's block library, with parameters* (recommended): the compiler is built on edakit's own data, projects
     change nothing, `block add` gains parameters.
   - *A project first*: the value shows earlier; the compiler is built on one project's needs.
3. **Designators.**
   - *Explicit in the source, allocated by the tool that writes a usage* (recommended): deterministic, the BOM and the
     board stable; a usage carries its designators.
   - *Allocated by the compiler and kept in the resolved graph*: shorter usages; the compiler needs the previous
     output, and a fresh clone needs the committed one.
4. **Expressions.**
   - *Arithmetic on quantities with units and ranges, `assert` as findings of DEF* (recommended): derivations become
     text; an evaluator with units to build.
   - *Values only, no expressions*: smaller; the derivation stays in Claude's head.
5. **Variants.**
   - *A variant file that redefines the main file, hashed as its resolved graph* (recommended): a few lines per
     variant, sign-offs that survive what does not reach them; a resolution across files.
   - *Complete files, as today*: nothing new; four times every change.
6. **SysML v2.**
   - *An export of the resolved graph, later, on request* (recommended): the standard gets a role without binding
     the source.
   - *Never*: nothing to maintain; no interoperability.
   - *As the source*: decision 1, second option.
7. **Building it at all.**
   - *When the triggers hold, stage 1 first* (recommended): the value is measured before the cost is paid.
   - *A prototype now, on the bell and led-bar, as the sketch was*: a decision on evidence sooner; a prototype that
     waits for the TOML form to have a target.
   - *Not at all*: TOML with names, `block add` with parameters as flags, `graph show` for slices.

Decided by Claude, for confirmation when the round comes: the compile target is the resolved graph of today's format;
attributes pass through; nets stay first-class and n-ary; `for` only over ranges, with `{n}` in names; no
conditionals and no I/O; the engine for what a definition asserts is DEF; a formatter and a grammar for highlighting
are deliverables of stage 1, not later; the language is optional per project, named by `[project] graph`.

## Sources

Read on 2026-10-31 from this session:

- atopile: [the repository](https://github.com/atopile/atopile) (README, `pyproject.toml`,
  `examples/auto-picking/auto-picking.ato`,
  [releases](https://github.com/atopile/atopile/releases), [tags](https://github.com/atopile/atopile/tags),
  [discussions](https://github.com/atopile/atopile/discussions)); the issues
  [#1821](https://github.com/atopile/atopile/issues/1821) and [#1827](https://github.com/atopile/atopile/issues/1827)
  with the contributor's statement on app.atopile.io; the third-party issue
  [Marwichmisi/NIA-PCB#3](https://github.com/Marwichmisi/NIA-PCB/issues/3) quoting the CLI message. Not reachable:
  docs.atopile.io, atopile.io, PyPI (a challenge page).
- faebryk: [the repository](https://github.com/atopile/faebryk) (README, releases, `examples/minimal_led.py`).
- SKiDL: [PyPI 3.0.0](https://pypi.org/project/skidl/3.0.0/). PCBDL: [the repository](https://github.com/google/pcbdl).
  codeyourpcb: [the repository](https://github.com/szymontex/codeyourpcb) and its
  [SYNTAX.md](https://github.com/szymontex/codeyourpcb/blob/main/docs/SYNTAX.md). tscircuit:
  [tsci export](https://docs.tscircuit.com/command-line/tsci-export). Not reachable: circuit-synth's documentation,
  JITX's site, the PHDL paper at OSTI.
- SysML v2: [the release repository](https://github.com/Systems-Modeling/SysML-v2-Release) with the
  [textual grammar](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/bnf/SysML-textual-bnf.kebnf),
  the [variability
example](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml/src/examples/Variability%20Examples/VehicleVariabilityModel.sysml)
  and the [vehicle example of Annex
A](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml/src/examples/Vehicle%20Example/SysML%20v2%20Spec%20Annex%20A%20SimpleVehicleModel.sysml)
  (`satisfy … by`, `verify`, `60 [kg]`); the OMG's
  [adoption announcement](https://www.omg.org/news/releases/pr2025/07-21-25.htm);
  [Syster](https://github.com/jade-codes/syster); the [resource list](https://github.com/daltskin/SysML-v2-Resources)
  naming Syside Automator and the ANTLR grammars. Not reachable: the OMG specification pages.
- edakit: handbook 14.5 (the blocks), `edakit/blocks/*.json`, `tests/reference.py`,
  [maker-coverage.md](maker-coverage.md) (the owner's projects, FT-23, FT-24, the stability of the model),
  [circuit-language.md](circuit-language.md) (the sketch, its review and decisions) and
  [circuit-language-plan.md](circuit-language-plan.md).
