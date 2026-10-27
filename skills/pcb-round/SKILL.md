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
   capacitors, LEDs, anything visible) is a fixed part. The plan's own `near` holds only between fixed parts. SMD
   parts under a module on pin headers: `on_headers`; SMD parts whose silkscreen outlines touch: `silk_overlap_mm`
   (handbook 7.4). Decoupling capacitors and the parts `layout.near` or `near` tie to a host: `edakit pcb place 2>&1 |
   cat` proposes a spot next to the host, `--write` adds the rows with `auto = true` (a later run may move those,
   never a row written by hand).
2. **Check offline before EasyEDA is touched:** `edakit pcb plan 2>&1 | cat` – overlaps, outline, holes, THT pins under
   parts of the other side, near-distances, the circuit's layout requirements (L-12), holes against leads (P-7),
   polarised parts turned as `uniform` says (default: LEDs in a row alike; a direction per kind for parts soldered by
   hand, handbook 7.4), airline length, net classes;
   look at `<artifacts>/pcb_plan_<board>.png` (Read) and show it to the user before `apply` when positions visibly
   change.
3. **EasyEDA** (start skill, claim EasyEDA):
   - New or swapped parts first: `edakit pcb parts --write`; then `edakit pcb dump` for their geometry if needed
     (dump turns all parts to 0°/TOP – afterwards always apply and the auto-layout again). Before they are in the
     PCB, `edakit part import <LCSC>` gives the plan of step 2 their library footprint; for a swapped part
     `edakit part diff OLD NEW` says how the new footprint lies over the old one (turn, shift, pad map).
   - `edakit pcb apply` (outline, holes, tooling holes, fixed parts locked; pad positions verified against the plan)
   - `edakit pcb autolayout` (unlocked parts, TOP only, waits for stable positions)
   - `edakit route all 2>&1 | cat` (read → DSN → Freerouting → check → apply → pours → reload → DRC; exit 0 = DRC 0).
     Open connections are yellow in `<artifacts>/route/<board>_routing.png`. Never EasyEDA's autorouter.
   - `edakit silk apply 2>&1 | cat` (designators where there is room; silkscreen on pads = 0; DRC). Through-hole parts
     of the other side, soldered from the designators side: `[silk] solder_side = true` (handbook 7.7). A part listed
     "without room": more room, a group label (`[silk] groups`) or `[silk] unlabelled` with the reason – the gate warns
     on it otherwise (L-17). Run it last, after the routing: the gate fails on edakit's own print on a mask opening.
4. **Check:** `edakit pcb nets` (pad nets = graph), DRC details in `<artifacts>/route/<board>_drc.json`. With sim.json
   `copper` (power nets whose track drop matters): `edakit sim 2>&1 | cat` on the new routing – the drop of the tracks
   is in every check now (handbook 5.2); a failure there goes back to the routing (wider class, a pour) or the circuit.
5. **Picture and review:** routing preview and silk pictures; a canvas capture may be stale. A round that changed
   placement, routing or pours ends with the agent pcb-reviewer in its own session, on this round's data: the plan,
   the routing files and the round's Gerber export `<artifacts>/gerber_<board>/` – the copper of every layer as
   EasyEDA filled it. `silk apply` writes that export; a round that did not run it runs `edakit silk check 2>&1 | cat`
   first. Its findings are fixed or decided (skill decision-round) before the next round and before the gate, not
   after it. A round that changed only the silkscreen may skip the review. At release the same agent signs M-5 on the
   gate run's files (skill release); its result is a sign-off, not a checklist for the user.
6. Save only when the state is better than the saved one; `route all` and `silk apply` save themselves.

## Known limits

- The auto-layout knows nothing about belonging: decoupling capacitors and pull-ups that must sit at their IC go into
  `place` – L-12 names the ones the circuit asks for, `pcb place` puts the ones with a host next to it.
- A pour polygon with a hole is taken only as its outer contour; tooling holes get a notch to the edge instead.
- The pours keep the tracks' edge clearance + 0.1 mm from the outline; `pour_inset_mm` in the board file gives them a
  distance of their own (handbook 7.6), e.g. further from the milled edge than tracks that run along it.
- Panel tabs: the remark and the tab zones in `[order]` of the board file belong to the layout. A new pour or a track
  along the edge can put copper into a tab zone – F-6 measures it at the gate, and `fab/<board>/order.md` lists the
  stretches that are still free (handbook 8.4).
- Two nets pouring on one layer: the one with priority fills it all unless `pour_regions = true` gives each its own
  area (handbook 7.6); an area enclosed by another net's is an error, solved in the routing.
- EasyEDA drops every pour piece without a pad of its net: where the pour net has no pad, that side stays bare. The gate
  warns (L-15: a copper-free circle above `[copper] max_bare_mm`, 5 mm); give the area a second pour net
  (`pour_regions`) or a pad or via of the pour net, then `route pours` again.
- While a free pad (tooling hole) is in the PCB, filling pours fails – edakit takes them out and puts them back.
- Net classes need the simulated currents (`edakit sim` first). `route check` holds the routed tracks and fixed wires
  to L-5 before anything is written; `[routing] widths = "sim"` routes at the IPC widths of the simulation instead of
  a hand-written class table (handbook 7.5).
- Freerouting cannot move a pad: pads of different parts on different nets closer than `clearance_mil` (L-13), or
  SMD pads on an assembled side closer than the paste gap (L-14, `[release] assembly` `paste_gap_mm`, 0.4 mm), stop
  `route all` at its check, without retries – move or turn one of the two parts in `place`.
- Freerouting is deterministic but order-dependent: `route all` retries with reshuffled DSNs when nets stay open.
  If it never closes: more room at the stuck pads in the plan, a plane for a power net (`fanout = true` for its SMD
  pads on the other side, handbook 7.5), or other layer costs; with all tracks on one side a 0 Ω bridge in the graph
  where a track has to cross (handbook 3.3), and the ground as a pour-only net (`pour_only`, handbook 7.6) that the
  pour between the tracks connects.

## Report

What changed, numbers (fixed parts, tracks, vias, DRC findings by kind; with `[looks]` the visible side's track length
and vias against its limits, handbook 7.5), picture, what the user must click (if
anything), whether it is saved, requests to the circuit. Note open layout items in the project's decision log.
