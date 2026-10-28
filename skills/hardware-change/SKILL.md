---
name: hardware-change
description: Carry a circuit change through completely – hardware graph, parts database, checks, simulation, the hand-over to the layout, documentation – and hand it to the PCB designer. Use when a part, value, net, pin, board assignment or a design decision is changed or added in an edakit project, also when the layout asks for a circuit change.
argument-hint: "<what changes>"
---

# Hardware change, end to end

The only source is the hardware graph (`[project] graph` in edakit.toml). **Never change the schematic or the PCB
directly** – EasyEDA content is generated and gets regenerated. Why: `${CLAUDE_PLUGIN_ROOT}/handbook/01-approach.md`,
format: `03-hardware-graph.md`. Change: $ARGUMENTS

This is the circuit designer's side. EasyEDA – schematic and PCB – is the PCB designer's, in a session of its own
(skill pcb-round, handbook 14.1); this skill ends with the hand-over.

## 0. Decision

- A new design decision gets the next free number (D-…) in the project's decision log with reason, date and the
  alternatives; cite the number in `notes` of the component or net.
- Several open questions: first a decision round (decision-round skill), then implement.
- Before proposing hardware: check that it fits – dimensions from the datasheet of the exact part (including solder
  tabs), against the board geometry. A proposal that does not fit wastes a round with the user.

## 1. Graph

Component: `designator`, `lcsc`, `board`, `type`, `pins` (number → name exactly as in the parts entry), `nc`, `value`,
`bom: false` for hand-soldered parts. Net: `name`, `pins` (`R1.2`), voltage range `v` over all operating states.
A new LCSC number without parts entry → part-search skill first. A part that replaces another one in the same
place: `edakit part diff OLD NEW 2>&1 | cat` before the graph changes (handbook 7.3) – it gives the pad map by position,
the roles that move, the holes and the graph change; take the map from it, not from the datasheet drawings. A board
of your own →
`edakit part own <its project>`, without an edakit project → skill own-part (handbook 4.5). A new function (an LED, a
button, a supply input, a transistor switch, I2C pull-ups) → `edakit block list` first; designing a function → skill
circuit-design.

## 2. Offline (seconds)

```bash
edakit check 2>&1 | cat     # ERROR: fix. WAIVED: only with a reason in the graph. PENDING blocks only the release
edakit hints 2>&1 | cat     # design hints of new parts: handle them or note why not ("hints" in the graph)
edakit stock 2>&1 | cat     # new or other parts: what JLCPCB says about them, dated – P-4 reads it in edakit check
edakit cost 2>&1 | cat      # what the change costs: class, Extended types, bake, X-ray – against [cost] budget
edakit sim 2>&1 | cat       # exit 2 = finding: find the cause, do not argue it away
```

`edakit check` explains every failed check below the findings; `edakit rules <ID>` gives the full entry.

Values quoted in documents and schematic notes (`[docs]`, handbook 6.6): `edakit docs` names the stale ones (G-19),
`edakit docs --write` fills them in – no sign-off is voided. With `[firmware]` in edakit.toml: `edakit firmware` writes
the firmware contract again (`--check` says whether it drifted, handbook 3.5) – commit it with the graph; the project's
renderer turns it into firmware source. Plus the project's own generated files and tests. A change of the protection
path or of a check also changes the tests that prove the check finds faults – run them, CI will otherwise find it later.

## 3. Hand-over to the layout

A part that is plugged in, pressed or seen, a helper that belongs to a pin, a hot loop: update `layout` in the graph
(circuit-design section 7). Then:

```bash
edakit schematic draw 2>&1 | cat   # the changed circuit as a drawing
edakit handover 2>&1 | cat         # what the PCB designer gets
```

A change of parts or of the power path is reviewed before the hand-over: the agent electrical-reviewer in its own
session, on this state – the changed circuit and the hand-over. Its findings are fixed or decided (skill
decision-round) first; the PCB designer takes over the reviewed state and the review's result, not a circuit whose
review is still to come after the layout. The release sign-offs stay as they are (skill release).

The PCB designer takes it over in its own session with the skill pcb-round – it brings the change into the EasyEDA
schematic and the PCB (`schematic create/layout`, `pcb parts/nets`) and checks the plan against the hand-over (L-12).

## 4. Documentation and sign-offs

- Circuit description / decision log / BOM notes of the project.
- Every change of graph, parts database or simulation config changes the circuit hash: sign-offs with scope
  'circuit' (e.g. M-1) no longer count and must be redone for the new state – by the agent, not the user. Keys in
  `[release] hash_ignore` (notes, sources, verified, …) are the exception: they are not in the hash. Never carry a
  hash forward by hand.
- A part swapped (another LCSC number): accepted warnings that name it in `parts` lapse – the protocol lists them;
  the user judges them again.

## 5. Finish

Commit graph, parts, generated files and docs together (the project's git workflow). Report: what changed, which checks
are green, what the hand-over asks of the layout, what the PCB designer has to bring into EasyEDA.
