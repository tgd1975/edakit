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

**KiCad** (`toolchain = "kicad"` in `[project]`, handbook 16): the same round with the same commands, on the board's
KiCad project – no start skill, no claim, no easyeda-operator, no *Import Changes*. `schematic create` writes and checks
the KiCad schematic; `pcb apply` writes parts, outline, holes and rules; KiCad has no auto-layout: the parts without a
row get one from `edakit pcb place --rest --write`. Everything below that names EasyEDA's GUI or the claim does not
apply.

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
                                              # (saved only when the netlist = graph)
edakit schematic check --schematic <board schematic> 2>&1 | cat
edakit pcb parts 2>&1 | cat                   # parts added, swapped or removed: show, then --write
edakit pcb nets 2>&1 | cat                    # only nets changed: show, then --write
```

An easyeda script (`[scripts]` in edakit.toml, handbook 8.6) changes the project library in EasyEDA – a footprint, a
module's device – and runs on command only: right after `schematic create`, before `schematic layout` and `pcb parts`
take the parts from the library, `edakit run <name> 2>&1 | cat` under the claim, when `edakit scripts` shows it
outdated or never run or `schematic create` brought new or swapped parts it changes. One that built a device the
template places needs `schematic create` once more. A project without entries skips this.

A part whose parts entry has `footprint_data` (an own footprint, handbook 4.5) gets its copy from the data at the same
place: `edakit part build <key> --write 2>&1 | cat` under the claim, right after `schematic create` and after every
change of the data. Parts already in the PCB keep their old copy – delete them, `edakit pcb parts --write`,
`edakit pcb dump` –, and `edakit check` holds the copy to the data (SYNC.footprint).

Before the PCB is linked: `edakit schematic copy` + `layout`. After that `copy` refuses (the PCB would lose its
schematic) and `layout` syncs parts in place. If parts were newly placed in the schematic, the DRC may show "Netlist
Error – Import Changes" until the import view was opened once in the GUI. edakit compares schematic and PCB then:
only when it says "EasyEDA waits for the import acknowledgement" (exit 3) request that click as the start skill
describes (section 3); a list of parts or pads is fixed with `pcb parts --write` / `pcb nets --write` first.

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
   parts of the other side, near-distances, the circuit's layout requirements (SYNC.plan), holes against leads (GEO.hole),
   polarised parts turned as `uniform` says (default: LEDs in a row alike; a direction per kind for parts soldered by
   hand, handbook 7.4), mated plugs of connectors whose parts entry has `mate` (clear of other parts, out through the
   outline), airline length, net classes; it writes `<artifacts>/mech_<board>.json` for the project's mechanics stage
   and enclosure scripts (handbook 7.4);
   look at `<artifacts>/pcb_plan_<board>.png` (Read) and show it to the user before `apply` when positions visibly
   change.
3. **EasyEDA** (start skill, claim EasyEDA):
   - New or swapped parts first: `edakit pcb parts --write`; then `edakit pcb dump` for their geometry if needed
     (dump turns all parts to 0°/TOP – afterwards always apply, which puts back every part with a row). The geometry
     lies beside the board file, `hardware/boards/<board>.geometry.json`, and is committed with it – the layout hash
     covers it, CI reads it. One that still lies among the artifacts (`pcb_geometry_<board>.json`) is named by
     `edakit check` and `pcb plan` with the `mv` that moves it; the next dump moves it too (handbook 7.4). Before they
     are in the PCB, `edakit part import <LCSC>` gives the plan of step 2 their library footprint; for a swapped part
     `edakit part diff OLD NEW` says how the new footprint lies over the old one (turn, shift, pad map). A footprint
     whose holes the project moves for leads formed by hand: `edakit pcb dump`, then `edakit check` – GEO.formed fails when
     a turn lays the formed holes onto themselves with a pin in another net's hole (handbook 3.3).
   - `edakit pcb apply` (outline, holes, tooling holes, fixed parts locked; pad positions verified against the plan)
   - `edakit pcb autolayout` (the parts without a row, TOP only; once they stand still it writes their rows into
     `[place]` with `auto = true` – commit them with the board file, `pcb plan` checks them like any row). Or
     offline, before EasyEDA is touched: `edakit pcb place --rest --write 2>&1 | cat` – edakit's own placer, by
     airline length, the same rows (handbook 7.4; on KiCad the only way). The auto-layout goes once the placer has
     placed a real board that routed and passed the gate; check the spots of `layout.fixed` parts it placed. A board
     placed before edakit wrote these back – SYNC.plan names its parts without a row – takes over its positions once,
     before any dump: `edakit pcb takeover --write`, fixed rows where the parts stand, the tracks stay on their pads
     (handbook 7.4)
   - `edakit route all 2>&1 | cat` (read → DSN → Freerouting → check → apply → pours → reload → DRC; exit 0 = DRC 0, 3 =
     only the import acknowledgement pending). Open connections are yellow in `<artifacts>/route/<board>_routing.png`.
     Never EasyEDA's autorouter.
   - `edakit silk apply 2>&1 | cat` (designators where there is room; silkscreen on pads = 0; DRC). Through-hole parts
     of the other side, soldered from the designators side: `[silk] solder_side = true` (handbook 7.7). A part listed
     "without room": more room, a group label (`[silk] groups`), a fixed spot (`[silk.place]`, tried offline with
     `edakit silk preview`) or `[silk] unlabelled` with the reason – the gate warns on it otherwise (GEO.silk). Run it
     last, after the routing: the gate fails on edakit's own print on a mask opening, and with `[looks]` on a
     designator shown on the visible side or a text there the board file does not put there (GEO.silk) – a part placed
     again after `silk apply` shows its designator until it runs again.
4. **Check:** `edakit pcb nets` (pad nets = graph), DRC details in `<artifacts>/route/<board>_drc.json`. With sim.json
   `copper` (power nets whose track drop matters): `edakit sim 2>&1 | cat` on the new routing – the drop of the tracks
   is in every check now (handbook 5.2); a failure there goes back to the routing (wider class, a pour) or the circuit.
5. **Picture and review:** routing preview and silk pictures; a canvas capture may be stale. A round that changed
   placement, routing or pours ends with the agent pcb-reviewer in its own session, on this round's data: the plan,
   the routing files and the round's Gerber export `<artifacts>/gerber_<board>/` – the copper of every layer as
   EasyEDA filled it. `silk apply` writes that export; a round that did not run it runs `edakit silk check 2>&1 | cat`
   first. With `[agents.<name>]` in edakit.toml (handbook 8.6) the project agent that replaces pcb-reviewer
   (`replaces`) reviews the round in place of pcb-reviewer, and the project's agents of the round review – a sign-off
   of scope `layout`, signed here on the round's layout hash – beside it: `edakit scripts 2>&1 | cat` shows who
   reviews where. The findings are fixed or decided (skill decision-round) before the next round and before the gate,
   not after it. A round that changed only the silkscreen may skip the review. At release the same agent signs M-5 on
   the gate run's files (skill release); its result is a sign-off, not a checklist for the user.
6. Save only when the state is better than the saved one; `route all` and `silk apply` save themselves.

**Project scripts** (`[scripts]` in edakit.toml, handbook 8.6; a project without entries skips this): `pcb place`,
`pcb parts`, `pcb plan`, `pcb apply`, `route all`, `silk apply` and `silk preview` run the input scripts that write
what they read – the board file, the silkscreen artwork – first when they are outdated, a line each under "project
scripts before …"; one that failed stops the step: fix it (its output is in `<artifacts>/scripts/<name>.log`).
`--no-scripts` is the exception, for a single run on purpose. A derive or easyeda script they name runs with
`edakit run <name>`; an easyeda script changes the project library in EasyEDA and runs on command only, under the
claim, after `schematic create` (section 0). After it the parts in the PCB keep their old footprint until deleted and
recreated: delete them, `edakit pcb parts --write`, `edakit pcb dump`, then the round as usual through `route all` –
`edakit check` warns until `pcb dump` and `route all` ran. Commit `hardware/scripts.lock` with what the scripts wrote.

## Known limits

- The auto-layout knows nothing about belonging: decoupling capacitors and pull-ups that must sit at their IC go into
  `place` – SYNC.plan names the ones the circuit asks for, `pcb place` puts the ones with a host next to it.
- A pour polygon with a hole is taken only as its outer contour; tooling holes get a notch to the edge instead.
- The pours keep the tracks' edge clearance + 0.1 mm from the outline; `pour_inset_mm` in the board file gives them a
  distance of their own (handbook 7.6), e.g. further from the milled edge than tracks that run along it.
- Panel tabs: the remark and the tab zones in `[order]` of the board file belong to the layout. A new pour or a track
  along the edge can put copper into a tab zone – FILES.order measures it at the gate, and `fab/<board>/order.md` lists the
  stretches that are still free (handbook 8.4).
- Two nets pouring on one layer: the one with priority fills it all unless `pour_regions = true` gives each its own
  area (handbook 7.6); an area enclosed by another net's is an error, solved in the routing.
- EasyEDA drops every pour piece without a pad of its net: where the pour net has no pad, that side stays bare. The gate
  warns (GEO.pour: a copper-free circle above `[copper] max_bare_mm`, 5 mm); give the area a second pour net
  (`pour_regions`) or a pad or via of the pour net, then `route pours` again.
- While a free pad (tooling hole) is in the PCB, filling pours fails – edakit takes them out and puts them back.
- Net classes need the simulated currents (`edakit sim` first). `route check` holds the routed tracks and fixed wires
  to GEO.width before anything is written; `[routing] widths = "sim"` routes at the IPC widths of the simulation instead of
  a hand-written class table (handbook 7.5).
- Freerouting cannot move a pad: pads of different parts on different nets closer than `clearance_mil` (GEO.spacing), or
  SMD pads on an assembled side closer than the paste gap (GEO.spacing, `[release] assembly` `paste_gap_mm`, 0.4 mm), stop
  `route all` at its check, without retries – move or turn one of the two parts in `place`. So do pads of other nets
  closer than `[routing] hand_solder_keep_mm` to a joint soldered by hand (`bom: false`) on its solder side – an SMD pad's
  the side its part sits on (GEO.spacing);
  vias are kept away there by the DSN (handbook 7.5).
- Freerouting is deterministic but order-dependent: `route all` retries with reshuffled DSNs when nets stay open. Before
  relaxing rules or moving parts, `edakit route diagnose 2>&1 | cat` says per open connection why: unreachable (what
  walls the pad in – a keep-out, the edge, a hole, foreign pads: no rule or pass count helps), blocked (by which nets,
  at what congestion: a crossing at low utilisation wants a bridge or the other layer) or a free way left (more passes);
  pictures in `<artifacts>/route/<board>_diagnose/` (handbook 7.5). If it never closes: more room at the stuck pads in
  the plan, a plane for a power net (`fanout = true` for its SMD pads on the other side, handbook 7.5), or other layer
  costs; with all tracks on one side a 0 Ω bridge in the graph where a track has to cross (handbook 3.3), and the ground
  as a pour-only net (`pour_only`, handbook 7.6) that the pour between the tracks connects.

## Report

What changed, numbers (fixed parts, tracks, vias, DRC findings by kind; with `[looks]` the visible side's track length
and vias against its limits, handbook 7.5), picture, what the user must click (if
anything), whether it is saved, requests to the circuit. Note open layout items in the project's decision log.
