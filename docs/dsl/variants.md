# Variants and requirements

!!! warning "A beta"
    The explorative DSL is a beta: it works only in a project that switches it on with `[beta] dsl = true` in
    edakit.toml, and its form may still change from one version to the next.

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
`decision D-8`; DOCS.ref resolves all of them (handbook 10.4).

## The requirement's keys of the DSL

In a project with the DSL switched on, a `[[requirement]]` of a TOML requirements file takes two keys more, and a
part or net of the graph two:

| Key | Of | Meaning |
| --- | --- | --- |
| `subject` | requirement | the part, net, usage or definition it is about (`led`, `+5V`); DOCS.ref resolves it against the graph and, for a `.circuit` graph, its usages and definitions |
| `require` | requirement | the condition as stated, kept as text and checked for its form – a quantity reference, an operator (`<`, `<=`, `>`, `>=`, `==`, `within`) and a quantity: `"D.i within 2 mA .. 15 mA"`; what checks it is what `verify` names |
| `satisfies` | part, net | the requirements it answers (`["R-3"]`); DOCS.ref holds them to the requirements of the files, `edakit req` lists a requirement's parts and nets |
| `decision` | part, net | the decisions it cites (`["D-8"]`); with `[release] publish.decisions` DOCS.ref holds them to the headings `## D-…` of the decision log |

A requirements file written in the notation, `hardware/requirements.circuit`, is read to the same entries and hashed
byte for byte as well.
