# 4 Design the circuit

After this step your circuit is text that has run through the checks and the simulation.

## What you do

Little: Claude designs. It reads what you said in the last step, picks the parts and computes the values. You start
it with `/edakit:circuit-design`, or with a sentence such as "add a buzzer".

Where one fits, Claude takes a [building block](../glossary.md#building-block), such as an LED with its resistor.
Every part gets a [parts entry](../glossary.md#parts-entry) with the limits from its datasheet. Common parts come
from edakit's parts library: `edakit part add` lists it, one line per part with its kind. Claude looks up a part the
library lacks at the shop and writes its entry from the datasheet.

## What you are asked

Only what Claude cannot settle by itself: what matters to you, such as cost, looks or how loud. Those questions come
in one round.

## What you see

The checks run in seconds:

```text
$ edakit check
domains: core, power (suggested by the graph – edakit domains)
PATH.reverse – reverse polarity blocked: 1 error (accepted)
…
4 components, 4 nets, 4 parts entries; 3 accepted; requirements: 2 needs, 2 requirements
```

Each result names its place and what to do. Then ngspice runs every case of the circuit. In the walkthrough these
are a fresh and a used cell, the button pressed or released, and the cell upside down.

```text
$ edakit sim
…
112 comparisons: pass 109, waived 3
```

## What you decide

Nothing yet. What the checks leave open comes to you in the next step.

## What you have

`hardware/graph.json`, the [hardware graph](../glossary.md#hardware-graph): every part, every net with its voltage
range, every pin by name. Next: [Decide on what was found](05-decide-on-what-was-found.md).

## Read on

- The walkthrough: [Circuit](../../handbook/17-walkthrough.md#175-circuit)
- The handbook: [Designing a circuit](../../handbook/14-design.md)
