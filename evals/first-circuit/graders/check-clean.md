---
type: llm
focus: trace
weight: 1
---

The trace shows the first and the last messages of the run. PASS if the last `edakit check` you can see ended
without an open error – its summary line (`N components, N nets, N parts entries; …`) counts nothing under `error` –
and the answer's `DONE:` line is that summary line. FAIL if that check shows an error, if no check ran, or if the DONE
line claims what the trace does not show. If no output of a check is visible to you, judge the DONE line on its own
and say so.
