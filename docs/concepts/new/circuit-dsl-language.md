# The circuit language: the notation, what it means, and its definition on SysML v2 and KerML

Status 2026-10-31: detail concept to [circuit-dsl.md](circuit-dsl.md), asked for by the owner the same day. It
fixes what that concept leaves to "the language": every construct with its syntax, its meaning, what it writes
into the resolved graph and the errors it raises; how the compiler resolves names and expands usages, loops and
variants; the derivation rules; the electrical library on SysML v2 that the notation is defined on and the
exports map to. It is written so that the session that builds it needs no question answered: where
circuit-dsl.md left a choice open, this document takes it and marks it "decided"; the owner confirmed the
seventeen decisions of section 12 on 2026-10-31. The toolchain – modules, commands, tests, the steps and their
order – is [circuit-dsl-toolchain.md](circuit-dsl-toolchain.md). Facts about edakit are those of main at
`2f4628a`, with the TOML form of circuit-language-plan.md built (L.1 to L.8, settled the same day); facts about
SysML v2 and KerML come from the specifications and the library files named in the sources. Against the
yardstick (CLAUDE.md): the source and the resolved graph are text in the project's repository; a model edits the
source through the CLI and `graph show`; nothing of the circuit lives only in EasyEDA or in someone's head.

## 1. The frame

- **One graph, two forms.** A project writes its circuit in the language (`hardware/graph.circuit`) or flat –
  `hardware/graph.toml` or `hardware/graph.json`, the forms of
  [circuit-language-plan.md](../done/circuit-language-plan.md), built on 2026-10-31 –; the compiler
  turns the language into the resolved graph in today's JSON format, which the engines, the simulation, the hash,
  the schematic, the firmware contract and the project's scripts read unchanged. The resolved graph is generated,
  committed and checked (section 8). The language adds one key to the graph, `derivations`.
- **Declarative, finite, without I/O.** The language has definitions, usages, ranges as loops, named derivation
  rules and variants as differences. It has no conditionals, no free expressions, no loops beyond integer ranges, no
  access to anything but the project's files and edakit's library. A compile is a function from the source files
  and the parts entries to the resolved graph: the same input gives the same bytes.
- **Two readers.** A model reads and edits the source, which stays short because definitions, loops and variants
  expand only when compiled; code reads the resolved graph. A reviewer reads both: the source for the intent, the
  diff of the resolved graph for the exact pins.
- **The owner's rule for the basis.** Every construct is an element of an electrical library defined in SysML v2's
  terms where they fit – part, port, connection, attribute, calc, requirement, metadata –, and in KerML's where
  they do not; the surface syntax is edakit's own, modeled on `.ato`'s ergonomics. So far nothing needed KerML
  directly (circuit-dsl.md, "KerML underneath"). The library (section 9) is the one artifact of the exports others
  could import.
- **What stays where it is.** Behaviour stays in the parts entries (SPICE), layout in the board files, parts data in
  the entries, the checks in the engines, the current through an LED in the simulation. The language composes; it
  decides nothing an engine decides.

## 2. Files and projects

| File | Role |
| --- | --- |
| `hardware/graph.circuit` | the main file of a project's circuit, named by `[project] graph` in edakit.toml; the extension `.circuit` is the language's, as clause 10.2 of KerML asks of a KerML-based language |
| `hardware/graph.json` | the resolved graph, written by `edakit graph json --write` beside the source as it is written beside a TOML graph – same directory, same stem, extension `.json` –, committed, checked by `--check` in the pre-commit hook and by SYNC.graph in `edakit check`; derived: in no hash and no data name, as the TOML form's (section 8) |
| files named by `include PATH` | further source files of the same project: definitions, a group of parts and nets; the path relative to edakit.toml, as every path in it |
| `variants/<name>/hardware/graph.circuit` | a variant: `variant NAME of PATH` names its base, the main file or another variant; the variant project has its own edakit.toml and its own resolved graph |
| `hardware/requirements.circuit` | needs and requirements in the notation, named by `[project] requirements` beside or instead of `requirements.toml` |
| `edakit/blocks/<name>.circuit` | edakit's building blocks as definitions; `edakit/blocks/<name>.json` stays the generated form `block add` reads (the toolchain plan, T.7) |
| a project's own definitions | in the main file or an included file; a definition of the project's shadows one of the library's of the same name |

Encoding UTF-8, lines ending in LF, no tabs; the formatter writes lines of at most 118 characters (the prototype's
width). Paths in the language are written as in edakit.toml, with `/`.

One namespace per project: designators, net names, parameter names, definition names, instance names and
requirement IDs are unique across the main file, its includes and the variant chain; a name twice is an error that
names both places. A variant redefines by naming an existing name; that is not a second declaration (section 5.9).

## 3. Lexical form

**Lines and statements.** A statement starts at the first column with a keyword; lines indented deeper than the
statement's first line belong to it (continuation lines), as the prototype's `statements()` reads them. A block
statement – `def`, `use`, `for`, `variant` – owns the indented lines as its body; inside a body the same rule
applies one level deeper. Indentation is spaces; the first continuation line fixes the indent of the statement's
continuation lines, a line indented less ends the statement. The formatter writes two spaces per level.

**Comments.** `#` to the end of the line, outside quotes. The formatter keeps comments: an own-line comment stays
before the line it precedes, an end-of-line comment stays on its line.

**Words.** A word is a run of characters without whitespace, `"` and `#`. Net names, pin words, designators, LCSC
numbers, codes, parameter names and bare values are words: `+5V`, `U1.PD6`, `U1.3V3(OUT)`, `LED_G1`, `C17630`,
`LIM.v`, `330Ω`, `4k7`. A word that starts with `(` opens a parenthesis group – `(locked)`, the parameter list of a
definition or a usage, whose items are separated by commas –; a lone `=` is the binding sign of usages,
parameters and aliases, while `=` inside a word is a pair (`1=1` of a cable, `1=TXD` of a pin map).

**Strings.** `"…"` with `\"` and `\\` as escapes; a line break inside quotes reads as one space, so a long text
wraps over continuation lines (the prototype's rule). A string stands where the reference says `"…"`; the first bare
string after a part's head is its label (section 5.2).

**Numbers** are integers or decimals with `.`; a quantity is a number with a multiplier, a unit or both (section 4).

**Pin words.** `DES.WORD`: the designator, a dot, and the pin's number, name or role, read as the Design reads every
pin word of a graph since L.1 of the TOML plan (`Design.resolve` in `edakit/design.py`): the number first, then the
name of one pin, then the role of one pin, then a name or role several pins share, which stands for all of them in
the entry's order; `U1.GND` on the Nano is pins 4 and 29. An alias of the part (section 5.2) is replaced by the
compiler before the Design reads the word. A word that names no pin is a compile error with the candidates –
stricter than the TOML form, which leaves it to STRUCT.pin so that a loaded graph is still checked (section 6).
`(locked)` after a pin word marks a pin the firmware relies on; it reaches the graph as `locks.pins`.

**Designators** are letters followed by digits (`R4`, `LED5`, `SW1`); **names** of nets, parameters, definitions
and instances are words; a definition's and a parameter's name is an identifier (`[A-Za-z_][A-Za-z0-9_]*`). Inside a
`for` body `{n}` and `{n+1}`, `{n-1}`, `{n*2}` with the loop's variable are substituted in words and strings
(section 5.7); braces elsewhere are text, so the block library's `{as}` passes through.

**Keywords** start a statement or name an attribute (section 5.12). A keyword is only read as one where the grammar
expects it: a net may be called `net` – nobody should, the formatter does not stop them –, because a net's name
follows the keyword `net`.

## 4. Quantities and units

The language reads quantities as edakit reads values today (`QUANTITY` and `MULTIPLIERS` in `edakit/circuit.py`),
extended by a unit table and by ranges and tolerances:

| Form | Examples | Meaning |
| --- | --- | --- |
| number, multiplier, unit | `330Ω`, `330 Ω`, `4k7`, `2R2`, `100nF`, `22 µF`, `10 mA`, `10mA`, `5 V`, `0.5 W`, `16 MHz`, `85 °C` | the multiplier may stand in for the decimal point (`4k7`); a space between number and unit is allowed |
| range | `0..5.5 V`, `2 mA .. 15 mA`, `0 V` | both ends in one unit – the unit may stand on the second end only –; `0 V` is the range `[0, 0]` |
| tolerance | `10 mA ± 20 %`, `3.3 V +/- 5 %` | the range `[x·(1−p), x·(1+p)]` |
| parameter name | `vlogic` | the value of a `param` or of a definition's parameter, read where a quantity is expected |

Units: `V`, `A`, `W`, `Ω` (also `ohm`, `ohms`, `R` as in `2R2`), `F`, `H`, `Hz`, `°C`, `s`, `m`, `%`; the names
of `[units]` in `edakit/catalog/kinds.toml` give the suffixes the entries use (`_v`, `_a`, `_w`, `_ohm`, `_f`,
`_h`, `_hz`, `_c`). Multipliers: `p n u µ μ m k K M G`. A quantity without a unit is a plain number, which `value`
of a part allows (`value 330Ω` and `value 330` both reach the graph as the text written, and STRUCT.identity reads
it against the entry as today).

Where quantities are read: the range of a net (`v`), `param` values, a definition's parameter defaults, the values
a usage passes, the arguments of a derivation, a requirement's `require`. A part's `value` stays text, as the graph
holds it today. Internally a quantity is `(lo, hi, unit)` with `lo == hi` for a point; a tolerance is a range. The
compiler refuses a unit where another is expected (`v 10 mA`) and a range whose ends are in different units.

## 5. The statements

Each statement: its form, what it means, what it writes into the resolved graph, its errors. `[…]` is optional,
`…` repeats, `|` separates alternatives; words in capitals stand for the user's text.

### 5.1 The graph as a whole

| Statement | Meaning and graph output |
| --- | --- |
| `graph NAME [version V] [date D]` | the first statement of a main file: `name`, `version`, `date` of the graph; a file whose first statement is `variant` is a variant (5.9) |
| `description "…"` | `description` |
| `purpose USE [market M] [notes "…"]` | `purpose.use` (private, gift or sale), `purpose.market`, `purpose.notes`; `set purpose.radio {…}` for the radio table |
| `convention KEY "…"` | `conventions.KEY`; the converter rewrites `pin_reference` for the word rule |
| `ground NAME`, `grounds NAME …` | `ground`, `grounds` |
| `accept KEY "reason"` | the graph's `accept`: `KEY` a code (`HINT.bulk`), a code with grade or topic (`LIM.i/margin`), or a quoted key with a place (`"HINT.bulk J2"`) |
| `lock PINWORD NET` | `locks.pins[pin] = NET` for a pin that sits on another net (a STRUCT.lock finding on purpose); the usual lock is `(locked)` in the net |
| `set KEY JSON` | any key of the graph as JSON – `set cables []`, `set locks.doc_pin_table {…}`, `set purpose.radio {…}`; a dotted key reaches one level down; the escape hatch for values without a form of their own |
| `include PATH` | reads another source file into the same namespace (section 6); only at the top level of a main file or an included file, never inside a block statement |
| `param NAME = QUANTITY` | a parameter of the project: `vlogic = 0..5.5 V`; read wherever a quantity is expected; a variant sets it again (5.9). Parameters leave no key in the graph: every net written with `vlogic` carries its value |

### 5.2 Parts

```text
part DES TYPE PARTNO [attributes…] ["label"]
  [nc PINWORD …]                                     # may repeat; pins by name, role or number
  [pins NUMBER=NAME …]                               # only where the graph's pin map differs from the entry's
  [alias NAME = PINWORD …]                           # the project's names for the part's pins
  [accept KEY "reason"]                              # the component's accept; may repeat
  [notes "…"]  [label "…"]  [KEY VALUE …]            # attributes, one or more per line
```

`DES` is the designator, `TYPE` the graph's `type` (`resistor`, `led`, `module`, … as handbook 3.1 lists them),
`PARTNO` the manufacturer part number or the value text the graph's `part` holds today (`"330 Ω 0805"`); `-` stands
for a missing `part`. Attributes are `KEY VALUE` pairs – `lcsc C17630`, `value 330Ω`, `board main`, `supplier rs`,
`spare 1`, `config NAME`, `source reversible`, `off_board`, `function "…"`, `notes "…"`, `label "…"` – and the
words `no-bom` (`bom: false`) and `bom yes` (back to the default, for a variant). A table or a list of the schema
(`states`, `strip`, `easyeda_device`) is written `set KEY JSON` on a continuation line. The first bare string after
the head is the `label`. The keys and their value kinds come from one table in the compiler (section 6, "The
attribute table"); a key the schema does not know is an error that names the nearest known key, so that a typo never
reaches the graph silently.

The pin map `pins` is written only where the graph's differs from the entry's; without it the Design takes the
entry's `{number: name}`, as it does for a TOML graph (L.2 of the TOML plan). Without an entry and without
`pins` the Design builds the map from the pin words its nets and `nc` use, so that the structure is checked and
STRUCT.entry reports the missing entry as today.

`alias` gives the project's names for pins of a module or IC: `alias led1 = PD6 led2 = PD5`. The right side is a
pin word of this part without the designator (name, role or number); the left side is read in every pin word of this
part before the entry's names, in nets, locks, `nc` and cables. The map is not in the graph; the resolved graph has
numbers. A variant that swaps the module writes the part again with its own `alias` lines (5.9).

Graph output: one component with `designator`, `type`, `part`, `lcsc`, `value`, `label`, `pins`, `nc` (numbers),
`bom`, `board`, `accept`, `notes` and every other attribute as written. `nc` and the nets give every pin its place;
a pin in neither is STRUCT.pin's finding, not the compiler's.

Errors: a designator twice (both places named); `nc` or an alias naming no pin of the entry; `pins` given for a
part with an entry whose names differ – not an error: STRUCT.entry reports it, as today.

### 5.3 Nets

```text
net NAME [RANGE | PARAM] [PINWORD [(locked)] …] [attributes…]
  [PINWORD …]                                       # a continuation line that starts with a pin word adds pins
  [accept KEY "reason"] [notes "…"] [fn spi.sck] [fn_bus LED] [bus i2c] [pwm_hz 1000] [KEY VALUE …]
  [without PINWORD …]                               # only in a variant: takes pins off the net
```

The range is `v`: `0..5.5 V`, `0 V`, a parameter name, or inside a definition `@PORT` – the range of the net on that
port at the usage, as the block JSON writes `"v": "@in"` today. A later `net NAME …` statement adds pins and
attributes the net does not have yet; a range or an attribute given twice is an error (the prototype's rule), except
in a variant, where a second value replaces the first (5.9). A pin word that stands for several pins (`U1.GND`) adds
all of them in the entry's order. `(locked)` after a pin word writes `locks.pins[pin] = NAME`.

Graph output: one net with `name`, `pins` (numbers, in the order written), `v` and the attributes; the nets in the
order of their first statement.

Errors: a pin word naming no pin or an unknown designator; the same pin in two nets or in a net and in `nc` – both
places named; a range in the wrong unit; `without` outside a variant.

### 5.4 Cables and the hand-over to the layout

As the prototype reads them, with pins by word:

```text
cable W1 J2 J1 1=1 2=2 r_ohm_per_wire 0.065           # name, from, to, pin pairs, the keys of CABLE_KEYS
layout fixed SW1 D2 D3                                # layout.fixed, .edge, .near, .loops, .apart, .notes
layout edge J1
layout near R1 U2
layout loop C5.1 U3.2 max_mm 8 "the hot loop"
layout apart +5V GND min_mm 2 "creepage"
layout note "…"
```

A cable's pairs are written `FROMPIN=TOPIN` with the word rule on each side. Graph output as today; `layout.loops`
and `apart` with pin numbers and net names.

### 5.5 Definitions

```text
def NAME [(PARAM = DEFAULT, …)] [ports PORT …]
  [title "…"] [about "…"]
  [port PORT "about"]                               # a port with its description; `ports` on the head is the short form
  part DES TYPE PARTNO …                            # the parts of the definition, as in 5.2
  net NAME [RANGE | @PORT] PINWORD …                # its nets; a net named in `ports` is a port
  derive TARGET … RULE(ARGS)                        # 5.8
  covers CODE …                                     # the codes the definition was checked against
  optional parts DES … | ports PORT …               # parts a usage may leave out, ports that may stay open
  notes "…"                                         # may repeat: what is left to decide
  set test {…}                                      # the block library's test table, passed through
```

A definition is today's block JSON written in the language – `name`, `title`, `about`, `ports` with their
descriptions, `components`, `nets`, `covers`, `optional`, `notes`, `graph` (`set graph {"grounds": […]}`), `test` –
plus parameters. A parameter has a name, a default (a quantity, a range or a word) and takes its unit from the
default; a usage may set it; a derivation reads it. A port is a net of the definition that the usage binds to a net
of the project; `gnd` is the conventional name of the port that joins the ground. A net of the definition that is no
port is internal and gets its name from the usage (5.6). Designators inside a definition are local names (`R`, `D`,
`R1`); the usage binds each to a designator of the project.

Definitions come from the project's files first, then from edakit's library (`edakit/blocks/*.circuit`); a
project's definition of a library name shadows the library's, and the compiler says so once as a note in its
output, not as a finding. A definition is not itself in the resolved graph; only its usages are.

Errors: a port not among the definition's nets; a part or net named twice; a `derive` whose target or rule the
definition does not have (5.8); a definition name twice in the project.

### 5.6 Usages

```text
use DEF INSTANCE [(PARAM = VALUE, …)] [bindings …]
  [bindings …]                                      # continuation lines
```

Bindings, in any order, each `LEFT = RIGHT`:

| Binding | Meaning |
| --- | --- |
| `PORT = NET` | the port's net is the project's net `NET`; the net is created if it does not exist, with the range the definition gives the port (`@PORT` chains resolve as in `block.plan`'s `v_of`); `gnd` without a binding joins the project's ground |
| `NET = NAME` | an internal net of the definition is named `NAME` instead of `<INSTANCE>_<NET>` in capitals (the bell's `anode = LED_G1_A`) |
| `PART = DES [attributes…]` | a part of the definition becomes the project's `DES`; the words after the designator belong to this part until the next binding – `lcsc`, `value`, `no-bom`, a label, `notes` –, and a part with more than an entry and a value goes on a continuation line of its own |
| `without PART …` | leaves out an optional part (`optional parts`); its pins leave the nets, a net left without pins is not made, and a pin left alone on an optional port that is not bound goes into its component's `nc` – `block.plan`'s rules |

Every part of the definition that is not left out must be bound to a designator (circuit-dsl.md item 10: the
designators are explicit, the compiler renumbers nothing). A parameter not set takes its default; a value outside
a parameter's unit is an error. A port not bound and not optional is an error; an optional port not bound stays
open as `block.plan` leaves it.

What the compiler makes of a usage: the definition's parts, in its order, each with the usage's designator and the
attributes the binding gives – the definition's attributes first, the binding's over them –; the definition's nets
with their pins renamed, ports joined to the bound nets, internal nets named; the derivations evaluated (5.8); the
`accept` keys of the definition with their places renamed (`block.rename_accept`). Nothing is appended to `notes`
– `block add` on a JSON graph appends "(block led, STATUS)" today, the compiler does not, so that a usage that binds
today's parts gives today's graph (the bell test of the toolchain plan). The parts and nets of a usage take the
position of the `use` statement in the graph's order.

Errors: an unknown definition; an unknown port, net or part in a binding; a designator bound twice or used by a
`part` statement too; a parameter the definition does not have; a derivation that fails (5.8).

### 5.7 Repetition

```text
for VAR in A..B
  part D{VAR+2} led KT-0805G lcsc C2297 value green "LED {VAR+1} (green 0805)"
  net LED{VAR} 0..5.5 V U2.OUT{VAR} D{VAR+2}.cathode
  net +5V D{VAR+2}.anode
```

`A` and `B` are integers, the range inclusive, `A ≤ B`. The body is expanded once per value with `{VAR}`,
`{VAR+k}`, `{VAR-k}` and `{VAR*k}` substituted in every word and string; a brace expression with another name or
another operator is an error. The body holds `part`, `net`, `use`, `lock`, `cable` and `layout` statements; a `for`
inside a `for`, a `def` or a `use` is not allowed (decided: nothing in the projects needs it; a second level is a
construct of its own later). `for` may stand in a main file, an included file and a variant. The expanded
statements behave as if written out: a `net +5V …` line adds pins to the existing net, a `part` statement is a new
part.

### 5.8 Derivations

```text
derive TARGET [TARGET …] RULE(ARG, …)
```

Inside a definition. `TARGET` is `PART.value` of a part of the definition; `RULE` one of edakit's derivation rules
(section 7); the arguments are the rule's inputs by name or position: a parameter of the definition, a quantity, a
part of the definition (`D`), a port (`in`). A rule's input the statement does not name is bound by the compiler
when the definition has exactly one candidate of the kind the rule asks for – the one LED, the one port other than
`gnd` –; otherwise the error says what to name. The number of targets is the rule's number of outputs.

What the compiler does with it, at every usage: evaluate the rule with the usage's parameter values, the bound nets'
ranges and the bound parts' entries; write a derivation record into the resolved graph's `derivations` (section 8);
leave the part's `value` as the usage binds it – the rule proposes, the designer chooses, DEF.derive reports a
value outside the rule's window. A definition without usages derives nothing. `block add --set` evaluates the same
rule for a JSON graph (the toolchain plan, T.8).

Errors, all at compile time with file and line: an input without a value (a port not bound, an entry without the
field the rule reads – `vf_typ_v` missing on the LED), a value outside the rule's range (a negative current, a
voltage below the LED's forward voltage), a unit that does not fit.

### 5.9 Variants

```text
variant NAME of PATH                      # the first statement of a variant file; PATH relative to edakit.toml
  …                                                   # statements of 5.1 to 5.8, each a redefinition or an addition
```

The variant's model is the base's model with the variant's statements applied in order, then compiled; a base that
is itself a variant resolves first (the chain in order). What a statement means in a variant:

| Statement | In a variant |
| --- | --- |
| `part DES …` with a designator of the base | redefinition: the attributes given replace the base's, the rest is inherited; a new `lcsc` or `part` brings the new entry's pin map unless `pins` is given; `nc` given replaces the list; `alias` lines given replace the map; `bom yes` sets the default back; `accept` keys given are added or replaced |
| `part DES …` with a new designator | an addition |
| `net NAME …` of a base net | the pins given are added, `without PINWORD …` takes pins off, a range or attribute given replaces the base's; `accept` keys as for parts |
| `net NAME …` new | an addition |
| `use DEF INSTANCE …` of a base usage | the parameter values and bindings given replace the base's for that usage – a part binding's attributes over the base's binding, as a part redefinition –; the definition cannot change |
| `param NAME = …` | the parameter's new value; every net and usage of the base that reads it follows |
| `description`, `purpose …`, `convention`, `accept KEY …`, `set KEY …` | replace the base's value of that key; `accept KEY -` removes an accept of the base |
| `include`, `def`, `for` | as in a main file: new files, new definitions, expanded statements that redefine or add |
| `graph …` | not allowed in a variant: the name, version and date are the base's unless `set name …` says otherwise |

A variant never renumbers and never removes a part; a configuration that drops a part writes a complete file of
its own (decided: the bell's variants replace, they do not remove). The resolved graph of a variant is complete –
every part, every net, every pin number – and is what its hash and its sign-offs bind to.

`[project] parts` of a variant project is a list of folders, the variant's first and then its base's; an entry is
looked up in that order (section 6). `[project] requirements` is a list already.

Errors: `without` naming a pin that is not on the net; a redefinition that names no part, net, usage or parameter of
the base and is no addition – `use` with an unknown instance, `param` with an unknown name –; a chain that loops; a
base file that is not a main file or a variant.

### 5.10 References

`satisfies R-3 [R-7 …]` and `decision D-8 [D-9 …]` are attributes of a part, a net or a usage: on a part or net they
reach the graph as `satisfies` and `decision`, lists of IDs; on a usage every part the usage binds carries them.
DOCS.ref resolves `satisfies` against the requirements files and `decision` against the decision log that
`[release] publish.decisions` names (the toolchain plan, T.16); without a requirements file or a decision log the
keys pass through unchecked.

### 5.11 Requirements

In a file named by `[project] requirements`, with the extension `.circuit`:

```text
need N-1 "The countdown is visible across the room." who owner [source "…"] [status accepted | draft | dropped]
  [reason "…"]
requirement R-3 from N-1 [D-8 …] must | should | may "Every countdown LED carries 2 to 15 mA while its step is on."
  [subject NAME]                                      # a usage, a definition (every usage of it), a part or a net
  [require QUANTITYREF within RANGE | QUANTITYREF < QUANTITY | …]   # the condition, stated, not evaluated
  verify rows "LIM.i *" | verify signoff M-1 | verify script NAME | verify accept "step"   # may repeat
  [source "…"] [status …] [reason "…"]
```

The same entries as `requirements.toml` holds today (`edakit/requirements.py`: `id`, `text`, `who`, `source`,
`status`, `reason`; `from`, `binding`, `verify`), plus `subject`, `require` and – derived from the graph's
`satisfies` – `satisfied_by`. The TOML form gains the same keys: `subject = "led"`, `require = "D.i within 2 mA ..
15 mA"`. `require` is parsed for its form – a quantity reference `PART.i`, `NET.v`, an operator or `within`, a
quantity or range with units – and kept as text; what checks it is what `verify` names, and DOCS.evidence holds a
requirement to having a `verify`, as today. `subject` is resolved by DOCS.ref against the resolved graph and the
source's usages and definitions.

Requirement statements are allowed only in files that `[project] requirements` names, never in the graph's source
(decided: the requirements files are hashed byte for byte, the graph's source only through its resolved graph, which
carries no requirements – a requirement in the graph's source would escape the circuit hash).

### 5.12 The keywords

Statements: `graph`, `description`, `purpose`, `convention`, `ground`, `grounds`, `accept`, `lock`, `set`,
`include`, `param`, `part`, `net`, `cable`, `layout`, `def`, `use`, `for`, `derive`, `variant`, `need`,
`requirement`. Inside statements: `nc`, `pins`, `alias`, `notes`, `label`, `no-bom`, `bom`, `without`, `ports`, `port`,
`title`, `about`, `covers`, `optional`, `parts`, `subject`, `require`, `verify`, `rows`, `signoff`, `script`,
`from`, `who`, `source`, `status`, `reason`, `must`, `should`, `may`, `within`, `in`, `of`, `satisfies`,
`decision`, `(locked)`, `V` after a range, `@` before a port. Attribute keys are the graph schema's (6, the
attribute table).

## 6. What the compiler does

`edakit graph json` reads the source set of a project and writes the resolved graph. Its phases, in order; every
phase collects all its errors before it stops, each error as `PATH:LINE: TEXT` with the statement named:

1. **Read.** The main file, every `include`d file (recursively, a file once), the variant chain's bases and the
   requirements files named by `[project] requirements` are read into statements with file and line (section 3).
   Lexical errors: an unterminated string, a tab, a continuation line without a statement, a brace expression
   outside a `for`.
2. **Namespace.** Definitions are collected from the project's files, then from `edakit/blocks/*.circuit`;
   parameters, designators, net names, instance names and requirement IDs are checked for a second declaration
   across all files of the set; `include` cycles are refused. A variant's statements are not declarations here
   (5.9).
3. **Variant chain.** A variant's base is resolved first – to its own flat model, recursively –; the variant's
   statements are applied to it in order: redefinitions merge, additions append (5.9). The result is one flat model
   of statements, as if written in one file.
4. **Parameters.** `param` values and the usages' parameter values are substituted wherever a quantity is expected;
   a name without a value is an error.
5. **Loops.** Every `for` is expanded (5.7); the expanded statements go through the same checks as written ones.
6. **Usages.** Every `use` is expanded in place (5.6): parts, nets, ports, optional parts, accepts.
7.  **Parts entries and pins.** The compiler replaces a part's aliases by the entry's words and leaves every
   other pin word as written; the graph it builds is read by the Design as a TOML graph's dict is
   (`graph_form.design_of`): the entry found as `Design.entry_key` finds it – by `lcsc` as the file name, else
   by `part` as the entry's `mpn` – in the folders of `[project] parts`, the first folder that has it wins; the
   pin map the entry's unless `pins` is given; every pin word in nets, `nc`, locks, cables and layout loops
   resolved to `DES.NUMBER` by `Design.resolve`. A word the Design leaves unresolved (`Design.unresolved`) is a
   compile error at its statement, with the entry's names and roles and the part's aliases as candidates; the
   resolved graph with numbers and the entries' pin maps is what `graph_form.resolved` gives.
8. **Derivations.** Every derivation of every usage is evaluated with the usage's values, the bound nets' ranges and
   the bound parts' entries; the records are written (section 7).
9. **Assembly.** The graph is assembled in today's key order – `name`, `version`, `date`, `description`, `purpose`,
   `conventions`, `components`, `nets`, `cables`, `layout`, `locks`, `accept`, `ground`, `grounds`, every `set` key
   where `set` put it – with `derivations` last; components in statement order, a usage's parts at the usage's
   position in the definition's order; nets in the order of their first mention, a net first created by a usage's
   port binding at the usage's position; the pins of a net in the order written; `nc` as numbers in the order
   written; `locks.pins` in the order the locks were written; `derivations` sorted by part, key and rule. The JSON
   is written as `block.write_json` writes a graph: `{"graph": …}`, indent 1, UTF-8 characters as they are, a
   trailing newline.
10. **Source map.** For every component, net, usage, lock, accept and derivation the compiler keeps the file and
    line of the statement that produced it, and for a usage's parts the usage's line and the definition's. The map
    stays in memory for the language server; `edakit graph json --map FILE` writes it on request (the toolchain
    plan, T.26); nothing of it is in the graph.

**The attribute table.** `edakit/lang/schema.py` holds the keys the language passes through, per object – the
graph, a component, a net, a cable, the layout – with the kind of value each takes: word, string, number, boolean,
quantity, range, list, table. It is the list of handbook 3.1 and the one place a new key of the schema is added; the
reader uses it to read `KEY VALUE` pairs and to refuse an unknown key with the nearest known one named, the
converter uses it to write a graph as statements, the formatter to order attributes. `set KEY JSON` bypasses it for
a table or a list, as the prototype's `set` does; the key must still be known.

**Determinism.** The compiler orders by statement order only – never by a set or by a dict's insertion order from
another source –, sorts what has no natural order (`derivations`), and uses one serializer. The toolchain's tests
compile every fixture twice and compare bytes, and compile with the files given in another order of `include`s with
the same result.

**What the compiler does not do.** It does not read the simulation config, the board files or the sign-off file; it
does not write parts entries (a missing entry is an error that names `edakit part add KEY`; `block add` copies
entries, the compiler does not); it does not allocate designators; it does not run the engines – `edakit check` does,
on the resolved graph.

## 7. The derivation rules

A derivation rule is a function of edakit's in `edakit/lang/rules.py`, registered with its name, its inputs (name,
kind, unit, how the compiler binds it when the statement does not), its outputs (the targets' kinds), the series it
chooses from and the window it declares acceptable. The compiler evaluates it; `block add --set` evaluates it for a
JSON graph; `edakit graph derive` re-evaluates the records of a graph against the entries as they are now; the
engine DEF reads the records only. A rule reads the parameters, the bound nets' declared ranges, the bound parts'
entries and the catalog's tables, and nothing else: no simulation, no sign-off, no file.

**The series.** `edakit/catalog/tables/series.toml` holds the E-series of IEC 60063 – E6, E12, E24, E96 – as
decades of mantissas, with the table's source and tag as every catalog table has them (`catalog.table_problems`
holds the file to it; the session that writes it reads the values from a source it names). A rule names the series it
proposes from; the record names the nearest value and the window.

**The record.** One per target per usage, in the resolved graph's `derivations`:

```json
{
 "part": "R4", "key": "value", "rule": "series_resistor",
 "from": "def led, use step1",
 "args": {"i": "10 mA", "led": "D", "in": "in"},
 "inputs": [
  {"name": "v_on", "value": 5.5, "unit": "V", "from": "net LED_G1 v[1]"},
  {"name": "i", "value": 0.01, "unit": "A", "from": "use step1 (i)"},
  {"name": "vf_typ_v", "value": 2.85, "unit": "V", "from": "C2895549 values.vf_typ_v"},
  {"name": "vf_min_v", "value": 2.6, "unit": "V", "from": "C2895549 values.vf_min_v"},
  {"name": "vf_max_v", "value": 3.1, "unit": "V", "from": "C2895549 values.vf_max_v"},
  {"name": "vf_at_a", "value": 0.005, "unit": "A", "from": "C2895549 values.vf_at_a"},
  {"name": "rs_ohm", "value": 10, "unit": "Ω", "from": "C2895549 values.rs_ohm"},
  {"name": "tolerance", "value": 0.01, "from": "C17630 values.tolerance"}
 ],
 "derived": {"value": 260.0, "unit": "Ω"},
 "series": {"name": "E24", "nearest": 270, "window": [240, 300]},
 "chosen": {"value": 330, "unit": "Ω", "from": "C17630 values.value_ohm"},
 "predicts": {"i": [0.0071, 0.0088], "unit": "A",
              "note": "at v_on 5.5 V, vf 2.6…3.1 V, R 330 Ω ±1 %; the driving pin's drop is not in it –
                       the simulation measures the current"}
}
```

`from` names the definition and the usage, never a line: a comment added above a statement must not change the
resolved graph and with it the circuit hash (decided). `inputs` carry every number the rule used and where it came
from, so that DEF.derive/inputs can tell a record whose entries have changed since, with numbers only. `chosen` is
the value of the part as the usage binds it, read through the entry as STRUCT.identity reads it. `predicts` is what
the rule says will happen with the chosen value; it is information, not a check.

**The rules of stage 1.** Formulas as the simulation's models use them (`edakit/sim/netlist.py`, `led_model`:
a diode with `RS = rs_ohm`, its forward voltage `vf` at `vf_at_a`), so that the rule and the simulation never
disagree about what an LED is.

| Rule | Inputs | Output and formula | Series, window |
| --- | --- | --- | --- |
| `series_resistor(i, led = D, in = in, series = E24)` | `i` the LED current (a quantity; a range or a tolerance gives its centre); `led` a part of kind `led` or `led_rgb` – default the one LED of the definition –, read for `vf_typ_v`, `vf_min_v`, `vf_max_v`, `vf_at_a`, `rs_ohm` (default 10, as `led_model`); `in` the port whose net drives the resistor – default the one port that is not `gnd` –, `v_on` its range's upper bound; the resistor's entry for `tolerance` (none: the prediction says so) | the resistor's `value`: `vf(i) = vf_typ_v + rs_ohm·(i − vf_at_a)`, `R = (v_on − vf(i)) / i`; predicts the current with the chosen `R` at the corners, `i_c = (v_on − vf_c + rs_ohm·vf_at_a) / (R·(1 ± tol) + rs_ohm)` with `vf_max_v` and `+tol` for the low end, `vf_min_v` and `−tol` for the high end | E24; one step of the series around the derived value (the neighbours of the nearest value) |
| `divider(v_out, i, in = in, series = E24)` | `v_out` the output voltage; `i` the divider's current; `in` the port whose range's upper bound is `v_in` | two targets, top and bottom: `R_bottom = v_out / i`, `R_top = (v_in − v_out) / i`; predicts `v_out` with the chosen values over the tolerance corners | E24; one step each |
| `pullup(v = in, i_sink = table, v_ol = table, c_bus, t_rise, series = E24)` | `v` the supply port's upper bound or a quantity; `i_sink` and `v_ol` default to the I2C table's `sink_a` and `vol_v` (`catalog/tables/i2c.toml`); `c_bus` and `t_rise` optional | one target: `R_min = (v − v_ol) / i_sink`; `R_max = t_rise / (0.8473 · c_bus)` with both given, else the table's `r_max_ohm`; the value nearest `sqrt(R_min · R_max)` | E24; the window `[R_min, R_max]` |
| `rc(f_c, c)` or `rc(f_c, r)` | the corner frequency and one of the two parts' values | the other: `R = 1 / (2π f_c C)`, `C = 1 / (2π f_c R)` | E24 for a resistor, E6 for a capacitor; one step |

A rule that cannot evaluate – `v_on ≤ vf(i)`, a missing field, a negative or zero input – is a compiler error at
the usage with the numbers; it is never a record.

**DEF, the engine.** `edakit/engines/derive.py`, prefix `DEF`, one code with a grade:

- `DEF.derive` (warning): a part's value is outside its record's window – "R4: value 330 Ω, derived 260 Ω by
  series_resistor (E24 270 Ω, window 240…300 Ω) – i 10 mA at 5.5 V, D vf 2.6…3.1 V"; the fix: another part of
  the series, or `accept` with the reason.
- `DEF.derive/inputs` (warning): a number in the record's `inputs` is not what its source says now – the entry's
  `vf_typ_v` changed, the net's range changed –; the fix: `edakit graph json --write` for a language source,
  `edakit graph derive --write` for a JSON graph.

The engine reads numbers only: it compares the part's value (through the entry, as STRUCT.identity) with the window,
and the record's inputs with the entries and nets of the design. It never evaluates a rule.

**A new rule** is knowledge, added with the skill add-rule and, from a project, proposed with propose-rule: the
function with its inputs, outputs, series and window; a test with numbers from a datasheet or a standard; a row in
the handbook's table of rules, generated from the rule table (`edakit/catalog/handbook.py`, kind `rules`); the
catalog table it reads, if any, with its source. A rule never picks a part, never reads the simulation, never writes
anything but its record.

## 8. The resolved graph and the hash

The resolved graph is today's graph (handbook 3.1) in every key, plus `derivations`, a list of records (section 7),
present only when the source has derivations. The engines ignore the key except DEF; `graph show` lists a part's
records under it (the toolchain plan, T.8); the converter writes records back as nothing – they are the compiler's.

**Loading and the hash.** `[project] graph` names the `.circuit` file and `Config.graph` is that source, as it
is the TOML file of a TOML project; `load_graph` reads a `.circuit` graph by compiling it – the project found
from the file (edakit.toml upward from it, its `[project] parts`, edakit's library) –, so that every reader of
the graph – the Design, the engines, the simulation, the gate, the scripts' data name `graph` – sees the
compiled graph as it sees a TOML graph's dict, and a compile error stops them as a broken TOML graph does, with
file and line. The circuit hash takes the compiled data as the TOML form takes a TOML graph's data (L.4:
`gate.content` with `graph=True` – arranged canonical JSON, pin words unresolved, `[release] hash_ignore`
applied, `purpose` and `compliance` whole); the generated `graph.json` is in no hash and no data name, as the
TOML form's. Since a variant's compiled data is its complete circuit, a change of the base reaches a variant's
hash only where it reaches the variant's circuit (circuit-dsl.md, value 4), and a comment or a reordered
statement changes nothing.

With `[project] parts` a list (a variant), the hash takes the entries the resolved graph uses – each from the
folder it was found in, named by its path relative to the project root – instead of every entry of a folder; with a
single folder, as today, every entry of the folder, so that no project without the list changes its hash (decided:
the concept's item 6 of the bell section, built so that "no key, no change" holds).

**Drift.** The resolved graph is derived and committed. `edakit graph json --check` exits 2 and lists what
differs when the committed file is not what the source compiles to; the pre-commit hook runs it (the hook line
of the TOML form, since L.8); `edakit check` reports the same as SYNC.graph (error, stage G), for a TOML graph
as for a language one – today only the hook guards the generated file –, so that a stale resolved graph never
passes a check or the gate unnoticed (decided, item 16).

## 9. The electrical library on SysML v2

`edakit/lang/library/Electrical.sysml` is the one artifact of the exports others could import: edakit's electrical
domain in SysML v2's terms, written once by hand, held by the conformance test (section 10), imported by every
exported project. It is written in the textual notation of the SysML v2 grammar (`SysML-textual-bnf.kebnf` of the
release repository) on the Systems Library – `Parts::Part`, `Ports::Port`, `Connections::Connection`,
`Attributes`, `Calculations::Calculation`, `Metadata::MetadataItem`, `Requirements`, `VerificationCases` – and the
Domain Libraries' quantities and units (`ISQ`, `SI`). The text below is the starting point; what the standard
reader accepts is what counts, and the session that builds it corrects the text to the reader, not the other way
round.

```sysml
library package Electrical {
    doc /* edakit's electrical domain: pins, components, nets, blocks, the circuit, its metadata, requirements and
         * derivation rules – what an edakit project is in SysML v2's terms. Generated into no project; imported
         * by every export of `edakit graph sysml`. */
    private import ScalarValues::*;
    private import ISQ::*;
    private import SI::*;

    attribute def Range { attribute min : ScalarQuantityValue; attribute max : ScalarQuantityValue; }
    attribute def VoltageRange :> Range {
        doc /* a net's v: min and max over all intended operating states */
        attribute :>> min : ElectricPotentialDifferenceValue;
        attribute :>> max : ElectricPotentialDifferenceValue;
    }
    enum def Purpose { private; gift; sale; }
    enum def Binding { must; should; may; }
    enum def Status { draft; accepted; dropped; }

    port def Pin {
        doc /* a pin of a component: the symbol's number, the entry's name and role */
        attribute number : String;
        attribute name : String[0..1];
        attribute role : String[0..1];
    }
    abstract part def Component {
        doc /* a component of the graph; the attributes are the graph's keys */
        attribute designator : String;
        attribute lcsc : String[0..1];
        attribute mpn : String[0..1];
        attribute value : String[0..1];
        attribute board : String[0..1];
        attribute bom : Boolean default true;
        attribute label : String[0..1];
        attribute notes : String[0..1];
        port pins : Pin[*];
    }
    part def Resistor :> Component { attribute resistance : ResistanceValue[0..1]; }
    part def Capacitor :> Component { attribute capacitance : CapacitanceValue[0..1]; }
    part def Inductor :> Component { attribute inductance : InductanceValue[0..1]; }
    part def Diode :> Component;
    part def LED :> Diode {
        attribute color : String[0..1];
        attribute vfTyp : ElectricPotentialDifferenceValue[0..1];
        attribute vfMin : ElectricPotentialDifferenceValue[0..1];
        attribute vfMax : ElectricPotentialDifferenceValue[0..1];
        attribute vfAt : ElectricCurrentValue[0..1];
        attribute rs : ResistanceValue[0..1];
        attribute ifMax : ElectricCurrentValue[0..1];
    }
    part def Microcontroller :> Component;   part def Module :> Component;      part def IC :> Component;
    part def Transistor :> Component;        part def Connector :> Component;   part def Regulator :> Component;
    part def Button :> Component;            part def Switch :> Component;      part def Potentiometer :> Component;
    part def Audio :> Component;             part def Testpoint :> Component;   part def BatteryHolder :> Component;
    part def Fuse :> Component;              part def Other :> Component;       // a graph type the library lacks

    connection def Net {
        doc /* a net: n-ary, every end a Pin; the attributes are the net's keys */
        attribute name : String;
        attribute v : VoltageRange[0..1];
        attribute fn : String[0..1];
        attribute fnBus : String[0..1];
        attribute bus : String[0..1];
        attribute pwmHz : FrequencyValue[0..1];
        attribute clockHz : FrequencyValue[0..1];
        attribute notes : String[0..1];
    }
    connection def Cable {
        doc /* wires between two connectors, pin to pin; the cable is no part */
        attribute name : String;
        attribute rOhmPerWire : ResistanceValue[0..1];
        attribute lengthM : LengthValue[0..1];
    }
    abstract part def Block :> Component {
        doc /* a definition of the language: ports, parameters, parts, nets, derivations */
    }
    part def Circuit {
        doc /* a project's graph */
        attribute name : String;
        attribute version : String[0..1];
        attribute date : String[0..1];
        attribute description : String[0..1];
        attribute purpose : Purpose[0..1];
        attribute market : String[0..1];
        attribute purposeNotes : String[0..1];
        attribute ground : String default "GND";
        part components : Component[*];
        connection nets : Net[*];
        connection cables : Cable[*];
    }

    metadata def Accept { attribute code : String; attribute reason : String; }
    metadata def Lock { doc /* the firmware relies on this pin being on this net */ attribute net : String; }
    metadata def Decision { attribute id : String[1..*]; }
    metadata def Layout { attribute fixed : String[*]; attribute edge : String[*]; attribute notes : String[*]; }
    metadata def Derivation {
        doc /* a record of section 7: the rule, its inputs as text, the derived value, the window */
        attribute rule : String;
        attribute inputs : String;
        attribute derived : Real;
        attribute unit : String;
        attribute window : Real[2];
    }

    requirement def CircuitRequirement {
        doc /* R-: one testable sentence as doc, with edakit's binding and status; verify names the evidence */
        attribute binding : Binding;
        attribute status : Status;
        attribute verify : String[*];
    }
    requirement def Need {
        doc /* N-: what someone wants, in their words */
        attribute who : String[0..1];
        attribute status : Status;
    }
    verification def Evidence {
        doc /* rows of the gate protocol, a sign-off, a script, an acceptance step */
        attribute what : String;
    }

    calc def SeriesResistor {
        doc /* R = (vOn − vf(i)) / i with vf(i) = vfTyp + rs·(i − vfAt): edakit's rule series_resistor */
        in i : ElectricCurrentValue;  in vOn : ElectricPotentialDifferenceValue;
        in vfTyp : ElectricPotentialDifferenceValue;  in vfAt : ElectricCurrentValue;  in rs : ResistanceValue;
        return r : ResistanceValue;
    }
    calc def Divider { in vIn : ElectricPotentialDifferenceValue; in vOut : ElectricPotentialDifferenceValue;
                       in i : ElectricCurrentValue; return rTop : ResistanceValue; return rBottom : ResistanceValue; }
    calc def Pullup { in v : ElectricPotentialDifferenceValue; in iSink : ElectricCurrentValue;
                      in vOl : ElectricPotentialDifferenceValue; return r : ResistanceValue; }
    calc def RC { in fC : FrequencyValue; in c : CapacitanceValue[0..1]; in r : ResistanceValue[0..1];
                  return rOut : ResistanceValue[0..1]; return cOut : CapacitanceValue[0..1]; }
}
```

What the text relies on, verified in the specification and the library files: `connection def Net` specializes
`Connections::Connection`, not `BinaryConnection`, and KerML 7.4.6 says "a connector with more than two ends can
also have more ends than any of its supertypes. However, a connector that specializes a binary association or
connector must itself be binary" – so a net usage `connection GND : Net connect (U1.GND, C1.minus, J1.'1')` with
any number of ends is a connection of the standard; `ElectricPotentialDifferenceValue`, `ElectricCurrentValue`,
`ResistanceValue`, `CapacitanceValue`, `InductanceValue` are `ISQElectromagnetism`'s and `ISQBase`'s (voltage is
the former's `attribute voltage : ElectricPotentialDifferenceValue`), `FrequencyValue` and `LengthValue`
`ISQSpaceTime`'s and `ISQBase`'s, all under `ISQ`; `V`, `A`, `'Ω'`, `F`, `H`, `W`, `Hz` are `SI`'s; `metadata
def` with attributes and a usage `@Accept { code = "LIM.v"; reason = "…"; }` is the grammar's `MetadataUsage` with
`MetadataBodyUsage` (`name = value;`); `calc def` with `in` and `return` parameters is `CalculationDefinition`; a
`doc` comment is `Documentation`. The calc definitions carry their formulas as documentation and no result
expression (decided: an expression over quantities with units is what a reader type-checks, and the record is data
in any case – the session adds the expression once the standard reader accepts it).

The names that SysML v2 reserves – `in`, `out`, `ref`, `part`, `port`, `connect` – and every name with a character
outside `[A-Za-z0-9_]` – `+5V`, `R-EXT`, `3V3(OUT)` – are written as quoted names, `'in'`, `'+5V'`, in every export.

## 10. The mapping and the exports

Every construct of the notation is an element of section 9's library. The table gives the construct, the library
element, the textual form `edakit graph sysml` writes and the KerML form `edakit graph kerml` writes; the exports
are one mapping applied twice, since SysML v2's abstract syntax specializes KerML's (`part def` is a `Structure`,
`part` a `Feature`, `connection` a `Connector`, `attribute def` a `DataType`, `metadata def` a `Metaclass`, `calc
def` a `Function`, `requirement def` a `Predicate`-based `Behavior`).

| Notation | Library element | SysML v2 textual | KerML textual |
| --- | --- | --- | --- |
| a project | `package 'christmas-bell'` with `import Electrical::*;` and `part def ChristmasBell :> Circuit { … }` | the package, the definition, its usages | `package` and `struct ChristmasBell :> Circuit` |
| `graph`, `description`, `purpose` | attributes of `Circuit` | `attribute :>> name = "christmas-bell";` … | `feature :>> name = "…";` |
| `part R4 resistor "330 Ω 0805" lcsc C17630 value 330Ω` | a `Resistor` usage | `part R4 : Resistor { :>> designator = "R4"; :>> lcsc = "C17630"; :>> value = "330Ω"; :>> resistance = 330 [SI::'Ω']; port '1' : Pin { :>> number = "1"; } port '2' : Pin { :>> number = "2"; } }` | `feature R4 : Resistor { … }` |
| a component of a type the library lacks (`testpoint` has one, a new type not) | `Other` with `attribute type` | `part TP1 : Other { :>> type = "…"; }` | the same |
| an attribute the library does not declare (`function`, `off_board`, a new key) | an attribute usage on the part, typed by its value | `attribute 'off_board' : Boolean = true;` | `feature 'off_board' : Boolean = true;` |
| `net +5V 0..5.5 V U1.5V C1.plus J1.2` | a `Net` usage with its ends | `connection '+5V' : Net connect (U1.'5V', C1.plus, J1.'2') { :>> name = "+5V"; :>> v = VoltageRange(min = 0 [SI::V], max = 5.5 [SI::V]); }` | `connector '+5V' : Net (U1.'5V', C1.plus, J1.'2') { … }` |
| a pin named by role in the source | the pin's port usage, named by the entry's name, with number and role | `port anode : Pin { :>> number = "1"; :>> name = "C"; :>> role = "anode"; }` | `feature anode : Pin { … }` |
| `(locked)`, `lock` | `@Lock` on the pin usage | `port PD6 : Pin { @Lock { net = "LED_G1"; } }` | the same with `@` |
| `accept KEY "…"` on a part, a net or the graph | `@Accept` on the usage or the definition | `@Accept { code = "LVL.undefined"; reason = "…"; }` | the same |
| `cable W1 J2 J1 1=1 2=2 …` | a `Cable` usage between the two connectors, the pairs as `doc` | `connection W1 : Cable connect J2 to J1 { :>> rOhmPerWire = 0.065 [SI::'Ω']; doc /* 1=1 2=2 */ }` | `connector W1 : Cable from J2 to J1` |
| `layout …` | `@Layout` on the definition | `@Layout { fixed = ("SW1", "D2"); edge = ("J1",); }` | the same |
| `def led (color = green, i = 10 mA) ports in gnd` | `part def Led :> Block` with attributes for the parameters (defaults), ports, parts, nets | `part def Led :> Block { attribute color : String default "green"; attribute i : ElectricCurrentValue default 0.01 [SI::A]; port 'in' : Pin; port gnd : Pin; part R : Resistor; part D : LED; connection anode : Net connect (R.'2', D.anode); … }` | `struct Led :> Block { feature color : String default "green"; … connector anode : Net (R.'2', D.anode); }` |
| `use led step1 (color = green) in = LED_G1 … R = R4 …` | a `part` usage typed by the definition, the parameters bound with `:>>` and `=`, its parts redefined with the designators, its ports ends of the project's nets | `part step1 : Led { :>> color = "green"; part :>> R { :>> designator = "R4"; :>> lcsc = "C17630"; } }` and `connection LED_G1 : Net connect (U1.PD6, step1.'in')` | `feature step1 : Led { :>> color = "green"; feature :>> R { … } }` |
| `for n in 0..7 …` | expanded: eight usages, eight connections; no element of its own (decided: the resolved graph has no loop, the export mirrors the resolved graph) | – | – |
| `param vlogic = 0..5.5 V` | an attribute of the circuit with a value; every net written with it carries the value too | `attribute vlogic : VoltageRange = VoltageRange(min = 0 [SI::V], max = 5.5 [SI::V]);` | `feature vlogic : VoltageRange = …;` |
| `derive R.value series_resistor(i)` and its record | `@Derivation` on the part usage, naming the `calc def` | `part :>> R { @Derivation { rule = "SeriesResistor"; inputs = "v_on 5.5 V, i 10 mA, vf 2.6…3.1 V"; derived = 260.0; unit = "Ω"; window = (240.0, 300.0); } }` | the same |
| `variant smd of …` | `package 'christmas-bell-smd'` importing the base's package, `part def ChristmasBellSmd :> ChristmasBell` with every redefinition as `:>>` | `part :>> LED5 : LED { :>> lcsc = "C2297"; :>> bom = true; }` | `struct ChristmasBellSmd :> ChristmasBell { feature :>> LED5 { … } }` |
| `alias led1 = PD6` | no element: the export writes the pins by the entry's names | – | – |
| `satisfies R-3` on a usage or part | `satisfy requirement 'R-3' by step1;` in the project's package; `decision D-8` as `@Decision { id = ("D-8",); }` | `satisfy 'R-3' by step1;` | `@Decision` only; satisfy is SysML's |
| `need N-1 …`, `requirement R-3 from N-1 must "…" subject led require … verify …` | `requirement 'N-1' : Need { doc /* … */ :>> who = "owner"; }`, `requirement 'R-3' : CircuitRequirement { doc /* the sentence */ :>> binding = must; subject led : Led; require constraint { doc /* D.i within 2 mA .. 15 mA */ } :>> verify = ("rows LIM.i *", "rows SIM.state *"); }` and a `#derivation` connection from `'N-1'` to `'R-3'` with the Requirement Derivation library's metadata | as written | KerML has no requirement: the kernel view writes them as `struct` usages of the library's `Predicate`-based definitions, the derivation as a `connector`; the KerML export is for the kernel view, the SysML export for the requirements |

**Quantities** are written in base SI units with the unit in brackets, `0.01 [SI::A]`, `330 [SI::'Ω']`, so that no
prefixed unit name has to exist in the library (decided). A range is a `VoltageRange` value; a tolerance is written
as the range it is.

**Identity.** Every exported element has a stable `@id` for the JSON format: the UUID version 5 of the project's
name and the element's qualified name (`christmas-bell::ChristmasBell::R4`), so that two exports of the same source
give the same ids and a diff of the JSON shows changes only.

**Files.** `edakit graph sysml [--out DIR]` writes `<artifacts>/sysml/<project>.sysml` and `<project>.json` – the
textual notation and the JSON serialization of clause 10.4 of KerML, an array of element objects with `@id`,
`@type` (the metaclass name, `PartDefinition`, `PartUsage`, `PortUsage`, `ConnectionUsage`, `AttributeUsage`,
`MetadataUsage`, `Documentation`, `OwningMembership`, `FeatureTyping`, `Redefinition`, `Subclassification`,
`LiteralString`, `LiteralRational`, `FeatureValue`, …) and the metaclass's properties, references as
`{"@id": …}` – and a copy of `Electrical.sysml` beside them; `edakit graph kerml` writes `<project>.kerml`,
`<project>.kerml.json` and `Electrical.kerml`, the kernel view with KerML's metaclasses (`Structure`, `Feature`,
`Connector`, `DataType`, `Metaclass`, `Function`, …). Both read the resolved graph and the source set – the
definitions, usages, parameters and requirements are the source's –; a JSON or TOML project exports as flat parts and
nets. The requirements export with the circuit.

**Conformance.** The test of stage 3 reads the library and an exported project with a standard reader and
expects no error: `systree.analyze(path).error_count == 0` (Syster's Python wrapper, `pip install systree`,
which installs `syster-cli` from crates.io on first use and so needs a Rust toolchain; alpha, MIT) for the
textual files, and `systree.import_file` for the JSON where its reader takes the clause-10 format – else a
structural check of edakit's own: every `@id` unique, every reference resolving, every `@type` a metaclass of
the language. The pilot implementation's reader joins as a second reader when its headless invocation can be
verified from the installers' documentation in the release repository (`install/`); if it cannot, it stays out,
and the plan says so. No acceptance test by a graphical tool: whoever imports the export into a SysML tool of
their own does so for their purpose, not as edakit's test (the owner, 2026-10-31). The test is an optional job
of the CI: it needs Rust and the network, and its failure does not block edakit's tests.

## 11. Examples

The texts the toolchain's tests use as fixtures. The example project led-bar (`tests/fixtures/led-bar`) in the
language, written from the prototype's translation of its graph and the constructs of this document:

```text
graph led-bar version 1.0 date 2026-10-25
description "Example for edakit: a Raspberry Pi Pico 2 drives eight LEDs through a TLC5916 constant-current sink; 5 V
    input with reverse-polarity diode, one push button."
purpose private market EU
  notes "An example board for edakit, built for testing, not sold or given away."
convention pin_reference "'<designator>.<pin>' with the pin's name or role, else its symbol number – the parts entry
    says which pin that is"
convention v "per net: [min, max] in V over all intended operating states"
convention accept "per net or component: {code: reason} accepts a finding on purpose (edakit explain <code>)"

part J1 connector B2B-PH-K-S(LF)(SN) lcsc C131337 no-bom source reversible "5 V input (JST PH, top entry)"
  notes "Pin 1 = VIN (+5 V), pin 2 = GND. Through-hole, soldered by hand (Economic assembly: SMD only)."
part D1 diode SS34 lcsc C8678 "Reverse-polarity protection"
  notes "A reversed supply reaches only the anode of D1."
part U1 microcontroller "Raspberry Pi Pico 2" lcsc C41407547 "Raspberry Pi Pico 2 (SMD module)"
  nc GP0 GP1 GP7 GP8 GP9 GP10 GP11 GP12 GP13 GP14 GP15 GP16 GP17 GP18 GP19 GP20 GP21 GP22 RUN GP26_ADC0 GP27_ADC1
  nc GP28_ADC2 ADC_VREF 3V3_EN VBUS SWCLK SWDIO TP1 TP2 TP3 TP4 GPIO25/LED BOOTSEL
  notes "GP2 (SPI0 SCK) and GP3 (SPI0 TX) clock and shift into the LED driver, GP4 latches, GP5 dims (PWM), GP6 reads
    the button (internal pull-up). The module's 3V3 regulator supplies U2."
part U2 ic TLC5916IDR lcsc C90107 "TLC5916 8-channel constant-current LED driver"
  nc SDO
  function "8-channel constant-current sink"
  notes "I_OUT = 15 x 1.26 V / R1 = 9.45 mA per output."
part R1 resistor 0805W8F2001T5E lcsc C17604 value 2k "R-EXT 2 k (sets the LED current)"
part R2 resistor 0805W8F1002T5E lcsc C17414 value 10k "OE pull-up 10 k: LEDs off until the firmware runs"
part C1 capacitor CC0805KRX7R9BB104 lcsc C49678 value 100nF "100 nF at U2 VDD"
part C2 capacitor CL21A226MAQNNNE lcsc C45783 value 22uF "22 µF on +5V at the module"
part SW1 button TS-1187A-B-A-B lcsc C318884 "Push button to GND"
  nc B D
  notes "Pins 1/2 and 3/4 are connected inside."

net VIN 0..5.5 V J1.1 D1.anode
  notes "5 V from a USB power supply, up to 5.5 V unloaded."
net +5V 0..5.5 V D1.cathode U1.VSYS C2.1
  notes "Behind D1: module VSYS and all LED anodes."
net GND 0 V J1.2 U2.GND R1.2 C1.2 C2.2 SW1.C U1.3 U1.8 U1.13 U1.18 U1.23 U1.28 U1.AGND U1.38 U1.42
net 3V3 0..3.4 V U1.3V3(OUT) U2.VDD C1.1 R2.1
  notes "From the module's regulator."
net LED_SDI 0..3.4 V U1.GP3 (locked) U2.SDI fn spi.tx fn_bus LED
  accept LVL.undefined "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
net LED_CLK 0..3.4 V U1.GP2 (locked) U2.CLK fn spi.sck fn_bus LED
  accept LVL.undefined "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
net LED_LE 0..3.4 V U1.GP4 (locked) U2.LE(ED1)
  accept LVL.undefined "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
net LED_OE 0..3.4 V U1.GP5 (locked) U2.OE(ED2) R2.2 fn pwm
  notes "Active low; R2 keeps the LEDs dark at boot."
net BTN 0..3.4 V U1.GP6 (locked) SW1.A
  notes "Internal pull-up of GP6; pressed = 0."
net REXT 0..1.3 V U2.R-EXT R1.1

for n in 0..7
  part D{n+2} led KT-0805G lcsc C2297 value green "LED {n+1} (green 0805)"
  net LED{n} 0..5.5 V U2.OUT{n} D{n+2}.cathode
  net +5V D{n+2}.anode

set cables []
layout fixed SW1 D2 D3 D4 D5 D6 D7 D8 D9
layout edge J1
layout near R1 U2
layout note "D2 to D9 form the bar: one row, in this order from left to right, as the user reads it."
```

Compiled, it equals led-bar's `hardware/graph.json` in canonical form – components by designator, nets by name, the
pins of a net sorted, pin numbers everywhere – with `locks.pins` from the `(locked)` marks; the order of the LED
parts and nets differs from the JSON's, which the canonical comparison does not see and the committed resolved graph
of the fixture fixes once.

A definition, two usages and a variant – the bell's LED step, as circuit-dsl.md models it, in the forms of this
document:

```text
def led (color = green, i = 10 mA) ports in gnd
  title "LED with series resistor, driven by a signal"
  part R resistor
  part D led value color
  net in     R.1
  net anode  R.2 D.anode    v @in
  net gnd    D.cathode
  derive R.value series_resistor(i)
  covers LIM.v LIM.i LIM.p LIM.t LIM.range LIM.declared LIM.backfeed LVL.threshold LVL.direction SIM.config SIM.state
  notes "sim.json: the driving net under the MCU's outputs, and leds_on in every load."

use led step1 (color = green)  in = LED_G1 gnd = GND anode = LED_G1_A
  R = R4   "330 Ω 0805" lcsc C17630 value 330Ω "Series resistor LED5"
  D = LED5 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 1"
use led step2 (color = green)  in = LED_G2 gnd = GND anode = LED_G2_A
  R = R3   "330 Ω 0805" lcsc C17630 value 330Ω "Series resistor LED4"
  D = LED4 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 2"
net LED_G1 vlogic U1.led1 (locked)
net LED_G2 vlogic U1.led2 (locked)
```

```text
variant smd of ../../hardware/graph.circuit
  description "… the SMD configuration"
  part J1 connector "HX PZ2.54-1x3P TP-YQ" lcsc C41417360 bom yes
  part C1 capacitor "RVT1C102M1010 1000uF 16V SMD" lcsc C3359 bom yes
  use led step1 D = LED5 KT-0805G lcsc C2297 bom yes "0805 LED, green, countdown step 1"
  use led step2 D = LED4 KT-0805G lcsc C2297 bom yes "0805 LED, green, countdown step 2"
  accept HINT.bulk "C1 1000 µF / 16 V electrolytic on +5V, next to J1 (it buffers the Nano's 5V pin)"
```

Requirements, in `hardware/requirements.circuit`:

```text
need N-1 "The countdown is visible across the room." who owner status accepted
requirement R-3 from N-1 must "Every countdown LED carries 2 to 15 mA while its step is on."
  subject led
  require D.i within 2 mA .. 15 mA
  verify rows "LIM.i *"  verify rows "SIM.state *"
  status accepted
requirement R-7 from D-8 should "A USB power bank stays on: the circuit draws at least 100 mA."
  subject +5V
  verify signoff M-1
```

## 12. Decided here

What this document decides beyond circuit-dsl.md, each with its reason – confirmed by the owner on 2026-10-31 in
the closing question of the round that wrote them: item 16 chosen among three alternatives (SYNC.graph for TOML
and language projects alike), the other sixteen acked as written:

1. `for` only at the top level of a main file, an included file or a variant, one level, over `part`, `net`, `use`,
   `lock`, `cable` and `layout` – nothing in the projects needs more, and a second level is a construct of its own.
2. The attribute keys the language passes through come from one table in the compiler; an unknown key is an error
   with the nearest known key named – a typo must not reach the graph silently; a new schema key is one line there.
3. The compiler appends nothing to `notes`; `block add` on a JSON graph keeps its suffix – a usage that binds
   today's parts must give today's graph.
4. Requirement statements live in requirements files only – they are hashed byte for byte, the graph's source only
   through its resolved graph, which carries no requirements.
5. A variant replaces and adds, never removes a part – the bell's four configurations need no removal; a
   configuration that drops a part writes a complete file.
6. `v_on` of `series_resistor` is the upper bound of the net on the driving port; the driver's drop is the
   simulation's; a record names its definition and usage, never a line, so that a comment changes no hash.
7. `block add` runs a block's derivation only with `--set`; without it the block's fixed value stands and no record
   is written – the projects at hand change nothing.
8. The export writes a derivation as `@Derivation` metadata naming the library's `calc def`, a variant as a
   definition specializing its base with `:>>`, quantities in base SI units with the unit in brackets, and no
   `variation` block – each the form a standard reader accepts without a model of edakit's own.
9. JSON ids are UUID version 5 of the project name and the qualified name – stable across exports.
10.  A language project's graph is hashed as a TOML graph's is – its compiled data, arranged, pin words
    unresolved –, the generated file in no hash; a project with a list of parts folders hashes the entries its
    graph uses, one with a single folder every entry of the folder.
11. `edakit req` reads `.circuit` requirements files; the TOML form gains `subject`, `require` and `satisfied_by`.
12. The extension is `.circuit`, lines end in LF, the formatter wraps at 118 characters; names with parentheses
    (`3V3(OUT)`) are words, a word that starts with `(` opens a group.
13. `require` is parsed for its form and kept as text; what checks it is what `verify` names.
14. The library's `calc def`s carry their formulas as documentation, not as result expressions, until a standard
    reader accepts the expressions.
15. The graph's `type` maps to one `part def` each; a type the library lacks maps to `Other` with the type as an
    attribute.
16.  SYNC.graph reports a stale generated `graph.json` in `edakit check` for TOML and language projects alike,
    as an error of stage G – today the pre-commit hook is the only guard of the generated file; a project
    without a generated file is not touched.
17.  A pin word that names no pin is a compile error of the language where the TOML form leaves it to STRUCT.pin
    – the compiler has the file and the line, while a loaded graph must still be checked.
18.  No acceptance test by a graphical SysML tool: the conformance test with a standard reader is the export's
    check; Eclipse SysON, a web application, stays a fact of the tool landscape and nothing more (the owner,
    2026-10-31, on the closing question).

## Sources

-  edakit at `2f4628a`: `edakit/graph_form.py` (`design_of`, `resolved`, `generated_path`, `main_json`,
  `to_toml`, `written`, `set_graph`, `main_convert`), `edakit/toml_edit.py` (`Doc`, `literal`, `line`),
  `edakit/design.py` (`load_graph`, `graph_of_toml`, `Design.resolve`, `word`, `pin_text`, `unresolved`),
  `edakit/release/gate.py` (`arranged`, `content` with `graph`, `state_files`, `file_hash`),
  `tests/test_pin_words.py`, `tests/test_graph_form.py`, `tests/test_graph_toml.py`, `tests/test_block_toml.py`,
  `edakit/circuit.py` (`QUANTITY`, `MULTIPLIERS`, `read_value`, `VALUE_PARAMS`, `VALUE_TOL`, `CABLE_KEYS`),
  `edakit/design.py` (`load_graph`, `entry_key`, `configured`), `edakit/block.py` (`plan`, `without_parts`,
  `rename_accept`, `write_json`), `edakit/blocks/led.json`, `edakit/engines/__init__.py`,
  `edakit/engines/struct.py`, `edakit/engines/quantities.py`, `edakit/findings.py`,
  `edakit/catalog/__init__.py`, `edakit/catalog/kinds.toml` (`[units]`, `[kinds.resistor]` with `tolerance`,
  `[kinds.led]`), `edakit/catalog/codes.toml`, `edakit/sim/netlist.py` (`led_model`, `led`),
  `edakit/engines/sim.py` (LIM.i on an LED, `led_on_min_a`), `edakit/config.py` (`PROJECT_KEYS`,
  `_requirements`, `[release] publish.decisions`), `edakit/requirements.py`, `edakit/graph_show.py`,
  `edakit/parts/C17630.json`, `edakit/parts/C2297.json`, `tests/fixtures/led-bar`, handbook 3.1, 10.1, 14.5; the
  prototype [translate.py and bell.circuit](../done/prototypes/circuit-language/) (`statements`, `Reader`,
  `Pins`, the width 118), its translation of led-bar; [circuit-language.md](../done/circuit-language.md) (the
  decisions, the rules of the round trip, "Every field of the graph");
  [circuit-language-plan.md](../done/circuit-language-plan.md) (settled: L.1 to L.8 built on 2026-10-31, its
  "State after the build").
- KerML 1.0 (formal/26-03-01): clauses 7.4.6 (connector ends), 7.4.13 (semantic metadata), 10.1 to 10.4 (model
  interchange, the file extensions, the JSON serialization: `@id`, `@type`, references, root namespaces), read from
  the specification's text on 2026-10-31; the SysML v2 textual grammar
  [SysML-textual-bnf.kebnf](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/bnf/SysML-textual-bnf.kebnf)
  (`ConnectionDefinition`, `ConnectionUsage` with `NaryConnectorPart`, `PartDefinition`, `PortDefinition`,
  `AttributeDefinition`, `CalculationDefinition` with `ReturnParameterMember`, `RequirementDefinition` with
  `SubjectMember` and `RequirementConstraintMember`, `SatisfyRequirementUsage`, `MetadataDefinition`,
  `MetadataUsage` with `MetadataBodyUsage`, `Documentation`, `LibraryPackage`, `AliasMember`, `VariantUsageMember`);
  the Systems Library files
  [Connections.sysml](https://github.com/Systems-Modeling/SysML-v2-Release/blob/master/sysml.library/Systems%20Library/Connections.sysml)
  (`Connection`, `BinaryConnection` with `source` and `target`), `Parts.sysml`, `Ports.sysml`, `Attributes.sysml`,
  `Calculations.sysml`, `Metadata.sysml`, `Requirements.sysml`, `VerificationCases.sysml`; the Domain Libraries
  `ISQBase.sysml` (`ElectricCurrentValue`), `ISQElectromagnetism.sysml` (`ElectricPotentialDifferenceValue`,
  `voltage`, `ResistanceValue`, `CapacitanceValue`, `InductanceValue`), `SI.sysml` (`V`, `A`, `'Ω'`, `F`, `H`,
  `W`, `Hz`), `Quantities.sysml` (`ScalarQuantityValue`), `RequirementDerivation.sysml`; all read on 2026-10-31.
- Syster's `systree` on [PyPI](https://pypi.org/pypi/systree/json): 0.4.4a0, Python ≥ 3.10, the README with
  `analyze`, `import_file`, `export_jsonld`, `export_kpar` and the CLI installed from crates.io on first use; the
  release repository's README for the pilot's installers; the installers' own README was not reachable from this
  session.
