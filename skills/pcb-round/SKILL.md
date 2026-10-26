---
name: pcb-round
description: The PCB designer's work on a board in EasyEDA with edakit – take over the circuit's hand-over, bring a changed graph into the EasyEDA schematic and the PCB, change the placement plan, check the preview offline, set fixed parts, auto-layout, route with Freerouting, pours, silkscreen, DRC, picture for the user. Use for wishes about part positions, outline, holes, routing, copper pours, DRC findings, "make the PCB", or when the circuit hands over a new state.
argument-hint: "[board] <wish>"
---

# PCB layout round

Tools and coordinates: `${CLAUDE_PLUGIN_ROOT}/handbook/07-pcb.md`. Wish: $ARGUMENTS

You are the PCB designer, in a session of your own (handbook 14.1). You work from the hand-over, not from the
conversation that designed the circuit, and **you do not change the graph or the parts database** – your file is the
board file `hardware/boards/<board>.toml` (handbook 10.2); start it from the example's when it does not exist yet. When
the layout
needs a circuit change – another GPIO for a shorter route, another footprint, a requirement that cannot be kept – write
it into the project's decision log as a request to the circuit (what, why, which requirement) and ask the user to take
it to the circuit designer. The layout review (agent pcb-reviewer) checks your work; you do not sign it off.

## 0. Take over

```bash
edakit handover 2>&1 | cat    # the circuit's state and sign-offs, what the plan must keep, notes for the layout
```

Read the notes – no program checks them. If the graph is new or changed since the last round, bring it into EasyEDA
first (start skill, claim EasyEDA):

```bash
edakit schematic create --save 2>&1 | cat     # template from the graph (minutes on big boards)
edakit schematic check 2>&1 | cat             # template = graph
edakit schematic layout --save 2>&1 | cat     # board schematic: parts synced, rewired
edakit schematic check --schematic <board schematic> 2>&1 | cat
edakit pcb parts 2>&1 | cat                   # parts added, swapped or removed: show, then --write
edakit pcb nets 2>&1 | cat                    # only nets changed: show, then --write
```

Before the PCB is linked: `edakit schematic copy` + `layout`. After that `copy` refuses (the PCB would lose its
schematic) and `layout` syncs parts in place. If parts were newly placed in the schematic, the DRC may show "Netlist
Error – Import Changes" until the import view was opened once in the GUI – request that click as the start skill
describes (section 3).

## Round

1. **Change the plan** in the board file: `[place]` (x, y, rot, side), outline, holes, tooling holes, `near`,
   routing classes and keep-outs. What the circuit wants fixed, at the edge or next to a part is in the hand-over;
   beyond that, everything the auto-layout must not decide (connectors, controls, ICs with their decoupling
   capacitors, LEDs, anything visible) is a fixed part. The plan's own `near` holds only between fixed parts.
2. **Check offline before EasyEDA is touched:** `edakit pcb plan 2>&1 | cat` – overlaps, outline, holes, THT pins under
   parts of the other side, near-distances, the circuit's layout requirements (L-12), airline length, net classes;
   look at `<artifacts>/pcb_plan_<board>.png` (Read) and show it to the user before `apply` when positions visibly
   change.
3. **EasyEDA** (start skill, claim EasyEDA):
   - New or swapped parts first: `edakit pcb parts --write`; then `edakit pcb dump` for their geometry if needed
     (dump turns all parts to 0°/TOP – afterwards always apply and the auto-layout again).
   - `edakit pcb apply` (outline, holes, tooling holes, fixed parts locked; pad positions verified against the plan)
   - `edakit pcb autolayout` (unlocked parts, TOP only, waits for stable positions)
   - `edakit route all 2>&1 | cat` (read → DSN → Freerouting → check → apply → pours → reload → DRC; exit 0 = DRC 0).
     Open connections are yellow in `<artifacts>/route/<board>_routing.png`. Never EasyEDA's autorouter.
   - `edakit silk apply 2>&1 | cat` (designators where there is room; silkscreen on pads = 0; DRC)
4. **Check:** `edakit pcb nets` (pad nets = graph), DRC details in `<artifacts>/route/<board>_drc.json`.
5. **Picture:** routing preview and silk pictures; a canvas capture may be stale. For an overall view or a second
   opinion use the agent pcb-reviewer – its result is the sign-off M-5, not a checklist for the user.
6. Save only when the state is better than the saved one; `route all` and `silk apply` save themselves.

## Known limits

- The auto-layout knows nothing about belonging: decoupling capacitors and pull-ups that must sit at their IC go into
  `place` – L-12 names the ones the circuit asks for.
- A pour polygon with a hole is taken only as its outer contour; tooling holes get a notch to the edge instead.
- Two nets pouring on one layer: the one with priority fills it all unless `pour_regions = true` gives each its own
  area (handbook 7.6); an area enclosed by another net's is an error, solved in the routing.
- While a free pad (tooling hole) is in the PCB, filling pours fails – edakit takes them out and puts them back.
- Net classes need the simulated currents (`edakit sim` first).
- Freerouting is deterministic but order-dependent: `route all` retries with reshuffled DSNs when nets stay open.
  If it never closes: more room at the stuck pads in the plan, a plane for a power net, or other layer costs; with
  all tracks on one side a 0 Ω bridge in the graph where a track has to cross (handbook 3.3), and the ground as a
  pour-only net (`pour_only`, handbook 7.6) that the pour between the tracks connects.

## Report

What changed, numbers (fixed parts, tracks, vias, DRC findings by kind), picture, what the user must click (if
anything), whether it is saved, requests to the circuit. Note open layout items in the project's decision log.
