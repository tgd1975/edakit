---
name: pcb-round
description: One layout round of a board in EasyEDA with edakit – change the placement plan, check the preview offline, set fixed parts, auto-layout, route with Freerouting, pours, silkscreen, DRC, picture for the user. Use for wishes about part positions, outline, holes, routing, copper pours, DRC findings or "make the PCB".
argument-hint: "[board] <wish>"
---

# PCB layout round

Tools and coordinates: `${CLAUDE_PLUGIN_ROOT}/handbook/07-pcb.md`. Wish: $ARGUMENTS

## Round

1. **Change the plan** in edakit.toml: `[boards.<b>.place]` (x, y, rot, side), outline, holes, tooling holes, `near`,
   routing classes and keep-outs. Everything the auto-layout must not decide (connectors, controls, ICs with their
   decoupling capacitors, LEDs, anything visible) is a fixed part.
2. **Check offline before EasyEDA is touched:** `edakit pcb plan 2>&1 | cat` – overlaps, outline, holes, THT pins under
   parts of the other side, near-distances, airline length, net classes; look at
   `<artifacts>/pcb_plan_<board>.png` (Read) and show it to the user before `apply` when positions visibly change.
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
  `place`.
- A pour polygon with a hole is taken only as its outer contour; tooling holes get a notch to the edge instead.
- While a free pad (tooling hole) is in the PCB, filling pours fails – edakit takes them out and puts them back.
- Net classes need the simulated currents (`edakit sim` first).
- Freerouting is deterministic but order-dependent: `route all` retries with reshuffled DSNs when nets stay open.
  If it never closes: more room at the stuck pads in the plan, a plane for a power net, or other layer costs; with
  all tracks on one side a 0 Ω bridge in the graph where a track has to cross (handbook 3.3).

## Report

What changed, numbers (fixed parts, tracks, vias, DRC findings by kind), picture, what the user must click (if
anything), whether it is saved. Note open layout items in the project's decision log.
