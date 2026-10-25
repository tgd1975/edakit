---
name: hardware-change
description: Carry a hardware change through completely – hardware graph, parts database, checks, simulation, schematics in EasyEDA, PCB parts and nets, documentation. Use when a part, value, net, pin, board assignment or a design decision is changed or added in an edakit project.
argument-hint: "<what changes>"
---

# Hardware change, end to end

The only source is the hardware graph (`[project] graph` in edakit.toml). **Never change the schematic or the PCB
directly** – EasyEDA content is generated and gets regenerated. Why: `${CLAUDE_PLUGIN_ROOT}/handbook/01-approach.md`,
format: `03-hardware-graph.md`. Change: $ARGUMENTS

## 0. Decision

- A new design decision gets the next free number (D-…) in the project's decision log with reason, date and the
  alternatives; cite the number in `notes` of the component or net.
- Several open questions: first a decision round (decision-round skill), then implement.
- Before proposing hardware: check that it fits – dimensions from the datasheet of the exact part (including solder
  tabs), against the board geometry. A proposal that does not fit wastes a round with the user.

## 1. Graph

Component: `designator`, `lcsc`, `board`, `type`, `pins` (number → name exactly as in the parts entry), `nc`, `value`,
`bom: false` for hand-soldered parts. Net: `name`, `pins` (`R1.2`), voltage range `v` over all operating states.
A new LCSC number without parts entry → part-search skill first.

## 2. Offline (seconds)

```bash
edakit check 2>&1 | cat     # ERROR: fix. WAIVED: only with a reason in the graph. PENDING blocks only the release
edakit sim 2>&1 | cat       # exit 2 = finding: find the cause, do not argue it away
```

Plus the project's own generated files and tests (firmware pin tables etc.). A change of the protection path or of a
check also changes the tests that prove the check finds faults – run them, CI will otherwise find it later.

## 3. Schematics (start skill first)

```bash
edakit schematic create --save 2>&1 | cat     # template from the graph (minutes on big boards)
edakit schematic check 2>&1 | cat             # template = graph
edakit schematic layout --save 2>&1 | cat     # board schematic: parts synced, rewired
edakit schematic check --schematic <board schematic> 2>&1 | cat
```

Before the PCB is linked: `edakit schematic copy` + `layout`. After that `copy` refuses (the PCB would lose its
schematic) and `layout` syncs parts in place (a swapped part keeps its UniqueId and the link to its footprint).

## 4. PCB

- Only nets changed: `edakit pcb nets --write`.
- Parts added, swapped or removed: `edakit pcb parts` (show), then `--write` – creates, swaps, deletes, links, copies
  the schematic properties, sets pad nets, measures the geometry, saves. No dialog. Then the pcb-round skill.
- If parts were newly placed in the schematic, the DRC may show "Netlist Error – Import Changes" until the import view
  was opened once in the GUI – request that click as the start skill describes (section 3).

## 5. Documentation and sign-offs

- Circuit description / decision log / BOM notes of the project.
- Every change of graph, parts database or simulation config changes the circuit hash: sign-offs with scope
  'circuit' (e.g. M-1) no longer count and must be redone for the new state – by the agent, not the user.

## 6. Finish

Commit graph, parts, generated files and docs together (the project's git workflow). Report: what changed, which checks
are green, what is left in EasyEDA.
