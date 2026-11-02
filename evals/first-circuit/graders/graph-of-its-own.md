---
type: llm
focus: {source: file, path: hardware/graph.json}
weight: 1
---

This is the graph the session wrote, `hardware/graph.json`. PASS if it is a circuit of its own for the idea "a 9 V
battery, a switch, two LEDs": a 9 V battery or its connector (a clip, a holder, a snap), a switch and two LEDs – a
resistor and more beside them are fine – and every finding accepted in it (`accept` on a component, a net or the
graph: `{code: reason}`) carries a reason that says why. FAIL if one of the three is missing, if it is the
walkthrough's coin-cell example (a CR2032, one LED, a button) taken as it is, or if an accepted finding has an empty
or meaningless reason.
