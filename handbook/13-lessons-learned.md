# 13 Lessons learned

From the reference project: a two-layer board of about 120 parts and 98 nets, with a second small board for a while,
built with Claude Code between 18 and 25 October 2026, for one order at JLCPCB without a prototype round.

## 13.1 Timeline

| Day | What happened | What we learned |
|---|---|---|
| 18 Oct | Decision: local EasyEDA Pro, automated through MCP, instead of drawing by hand | EasyEDA Pro has no CLI and no HTTP API; the extension API inside the editor is the only door |
| 19 Oct | MCP server set up; parts chosen; the graph becomes a pin-level netlist; scripts: schematic from the graph, schematic ↔ graph check, copy, topology layout | exact LCSC match (full-text search); symbol pin numbers differ from datasheets for LEDs |
| 20 Oct | Verification pipeline: parts database, rule checks, ngspice simulation, release gate; second board; `batch_write`, focus guard, guarded renaming; sides swapped so the auto-layout (TOP only) can work | renaming acts on the active schematic; big batches crash EasyEDA; the auto-layout ignores belonging |
| 21 Oct | Fixed-part plan, LED-to-channel assignment by wire length, pours; EasyEDA autorouter + a tool to repair GND islands from the Gerber export | the autorouter discards everything on failure; repairing its result does not converge |
| 22 Oct | Bridge patch (return depth 12); routing with Freerouting from our own DSN; EasyEDA unthrottled; 120-s bridge timeout; EasyEDA claim between sessions; parts without the import dialog; silkscreen; release gate on the real manufacturing files; second datasheet check by an agent | the most productive day – each fix removed a class of problems instead of a symptom |
| 23 Oct | Layout review by an agent: switching loop 61 mm long, visible side crowded → compact loop, quieter side, L-11; USB-C input; release gate passed | an automatic gate without a layout review released a layout nobody had looked at |
| 24 Oct | Part swaps for stock and price, gate passed again; order list | a gate run is routine – a cheaper part is worth one |
| 25 Oct | Power concept redesigned (one board instead of two): graph, schematic, PCB, routing within a day; tooling holes for Economic PCBA | the pipeline makes even a redesign a matter of hours |

## 13.2 Where the time went

Measured over four change runs on 22–23 October (wall clock from request to commit):

| Change | Wall clock | Active work | In EasyEDA | Waiting | Biggest sink |
|---|---:|---:|---:|---:|---|
| a connector swapped on the small board | 1 h 45 min | ≈ 15 min | ≈ 7 min | ≈ 93 min | EasyEDA held by another session (83 min) |
| an LED's polarity fixed through the nets | 44 min | ≈ 40 min | 38 min | 3.5 min | two dead ends trying to edit a library footprint (≈ 25 min) |
| layout round: switching loop, calm side, silkscreen | 2 h 30 min | ≈ 2 h 20 min | 48 min | ≈ 4 min | offline routing experiments (≈ 90 min), hanging wait loops (≈ 15 min) |
| USB-C input on the small board | 2 h 07 min | ≈ 45 min | 68 min | ≈ 100 min | waiting for one click (49 min, EasyEDA held meanwhile) |

Typical step times: graph change and offline checks 5–15 s; schematic generation 12–41 s (13 parts) and 6 min
(123 parts); board schematic layout 3–10 s and 2–3 min; Freerouting run 1.5–4.5 min per attempt, creating ~1700 track
pieces 1.2 min; silkscreen 25 s; gate with EasyEDA under 1 minute to 5 minutes; pre-commit hook 15 s.

**The lesson:** the work itself was fast. The time went into waiting for the shared EasyEDA, waiting for a click,
dead ends against the API, and loops that never ended. Each got a rule or a tool:

1. **EasyEDA is one shared resource** → a claim per session, automatic on first access, expiring after 15 minutes;
   short runs may be let in between two long ones and EasyEDA comes back afterwards.
2. **Clicks** → avoid them through the API (parts and nets without the dialog); release EasyEDA while waiting for a
   click; ask the user when they are there; the click is a plain OK.
3. **Wait loops with `pgrep -f`** found their own shell and never ended – six times, ten minutes each, and one aborted
   run went unnoticed for 11 minutes → wait for an end line or the PID.
4. **Library footprints cannot be repaired through the API** → change the graph (which pad gets which net) and let
   everything follow.
5. **Regenerating a big schematic costs ~9 minutes per change** → only the board schematic is rebuilt for layout
   changes; parts sync in place.
6. **A generated schematic drifted** (a pin on two nets) without anyone writing to it → the reference schematic is
   checked at the start of every EasyEDA session and before every gate run.
7. **Checks missing in the flow** (the hardware tests did not run after a graph change; CI found it) → the pre-commit
   hook runs the fast hardware tests whenever hardware files are staged.
8. **Small things with consequences:** API connection errors that stalled a session until the user typed "continue";
   a gate stage that did not wait for the bridge; `tail -3 a b` failing with a newer coreutils; output filtered so
   hard that an abort was invisible.

## 13.3 What we would do again

- **The graph as the only source.** Every change was a few lines of JSON plus a pipeline run. A redesign of the power
  concept took a day.
- **Checks at every hand-over, the last one on the Gerber files.** The copper connectivity check from the Gerber
  export never trusted EasyEDA and caught what the DRC could not explain.
- **Freerouting with our own DSN.** Deterministic, offline, checkable before anything is written. Reshuffling the
  order on failure solved what looked like unroutable nets.
- **Independent agents for the judgement calls**, and their result as the sign-off. The second datasheet check found
  a footprint with "+" at the cathode and two holes too small for their leads; the layout review found the 61-mm
  switching loop. All three would have hit every board.
- **Numbered decisions** with reasons in the user's words. Sessions days later knew why a track is thinner than its
  class and that it was accepted.
- **Fix the cause, not the symptom.** Throttling, the bridge timeout, the return depth – each took an hour to find
  and removed a whole family of failures.

## 13.4 What we would do differently

- **Freerouting from day one.** A day went into EasyEDA's autorouter and into repairing its leftovers (GND islands,
  ripped-up nets, GND-first routing). None of it survived.
- **The layout review as a gate condition from the first release**, not after the first released run.
- **The EasyEDA claim before the second parallel session**, not after a lost 20-minute run.
- **Tooling holes and the assembly type (Economic vs Standard) in the first layout**, not after the first quote – they
  constrain where parts can go.
- **Check the target before writing.** On the second project `createProject` silently returned null and the first
  generated schematic landed in the reference project (removed a minute later). Every write path now starts with
  "is the open project the configured one?".
- **Generic from the start.** The scripts began full of project constants (outline formula, LED channels, decoration).
  This repository is the generic extraction; a new project starts with an edakit.toml instead of a copy of scripts.

## 13.5 Numbers

- 7 days from the first MCP call to a redesigned, routed board; first released manufacturing files after 5 days.
- ~120 parts, 98 nets; routing ~1500 track pieces, ~220 vias, DRC 0.
- Simulation: 41 scenarios, ~11 000 single checks in about 3 seconds.
- Release gate: 7 stages, about 30 automatic checks in the board and manufacturing stages alone, 5 manual checks of which 2 are done by
  agents before the export.
- About 25 EasyEDA API behaviours that cost time to find out (chapter 9).

## 13.6 The second project

The first project after the extraction was much smaller: [the Christmas bell](https://github.com/tgd1975/automatic_christmas_bell), a carrier board for a
plugged-in Arduino Nano with a servo, five LEDs and two buttons, taken over from a Fritzing drawing. The circuit itself was quick: graph, parts and simulation took
under an hour. Most of the time went into what the bell exposed in edakit, which had to be built before the board
could go through:

- **Off-board loads** in the simulation (`external`: the servo at its connector) and **fault cases** that do not block
  every commit (`"matrix": false`): a stalled servo draws more than the Nano's 500 mA polyfuse holds.
- **5 V I/O modules** (`v_io = "vin"`) and an **input level check**: the buttons switched 3.3 V into a 5 V AVR,
  0.28 V above its VIH – visible now, and moved to 5 V.
- **Pin names** are compared with the symbol: it caught three LED entries whose names disagreed with their symbols –
  one library series marks the anode with "+" on pad 1 for green and red and on pad 2 for yellow.
- **LEDs side by side point the same way** (plan check), after the first silkscreen showed the yellow ones turned.
- **A new project's default board** is adopted, and **project creation is manual** in the local desktop client
  (chapter 9.2) – with a guard after the first generated schematic landed in the wrong project.
- The gate's hole check (L-9) failed the Nano footprint from a user library: 0.9 mm holes for 0.64 mm square header
  tails. Library footprints are not checked by anyone else.
