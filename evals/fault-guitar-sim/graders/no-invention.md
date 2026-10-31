---
type: llm
weight: 1
---

PASS unless the answer attributes to edakit something edakit did not output in this run – a finding, a code, a
number or a rule that does not appear in the trace's `edakit check`, `edakit sim` or `edakit explain` output – or
states something about the circuit that is wrong (for example calls a part what it is not). Explanations, the
agent's own reasoning and suggested fixes are fine, also when they go beyond edakit's output, as long as they are not
presented as edakit's findings.
