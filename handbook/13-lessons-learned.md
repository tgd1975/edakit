# 13 Lessons learned

For anyone who wants to know where edakit comes from and why its rules are as they are. You find the two projects it was
built on, day by day, where the time went, what we would do again and differently, and how the details of the other
chapters came about. The short way: [the steps](../docs/steps/README.md).

edakit was grown on [pytree](../docs/projects/pytree.md), a programming advent calendar with a tree of circuit boards:
a project of about 120 parts built in October 2026. Its board has two layers and 98 nets – an MCU module, three LED
driver ICs, about 30 LEDs, buttons, a DIP switch, a buzzer and a concave decorative outline –, assembled by JLCPCB on
one side, with a second small board for a while. It was built with Claude Code between 18 and 25 October 2026, for one
order at JLCPCB without a prototype round, so the gate had to catch everything that would hit all boards alike.

## 13.1 Timeline

| Day | What happened | What we learned |
|---|---|---|
| 18 Oct | Decision: local EasyEDA Pro, automated through MCP, instead of drawing by hand | EasyEDA Pro has no CLI and no HTTP API; the extension API inside the editor is the only door |
| 19 Oct | MCP server set up; parts chosen; the graph becomes a pin-level netlist; scripts: schematic from the graph, schematic ↔ graph check, copy, topology layout | exact LCSC match (full-text search); symbol pin numbers differ from datasheets for LEDs |
| 20 Oct | Verification pipeline: parts database, rule checks, ngspice simulation, release gate; second board; `batch_write`, focus guard, guarded renaming; sides swapped so the auto-layout (TOP only) can work | renaming acts on the active schematic; big batches crash EasyEDA; the auto-layout ignores belonging |
| 21 Oct | Fixed-part plan, LED-to-channel assignment by wire length, pours; EasyEDA autorouter + a tool to repair GND islands from the Gerber export | the autorouter discards everything on failure; repairing its result does not converge |
| 22 Oct | Bridge patch (return depth 12); routing with Freerouting from our own DSN; EasyEDA unthrottled; 120-s bridge timeout; EasyEDA claim between sessions; parts without the import dialog; silkscreen; release gate on the real manufacturing files; second datasheet check by an agent | the most productive day – each fix removed a class of problems instead of a symptom |
| 23 Oct | Layout review by an agent: switching loop 61 mm long, visible side crowded → compact loop, quieter side, GEO.loop; USB-C input; release gate passed | an automatic gate without a layout review released a layout nobody had looked at |
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
(123 parts: placing 2.1 min, connecting 3.7 min); board schematic layout 3–10 s and 2–3 min; Freerouting run
1.5–4.5 min per attempt, creating ~1700 track pieces 1.2 min; silkscreen 25 s; gate with EasyEDA under 1 minute to
5 minutes; pre-commit hook 15 s.

**The lesson:** the work itself was fast. The time went into waiting for the shared EasyEDA, waiting for a click,
dead ends against the API, and loops that never ended. Each got a rule or a tool:

1. **EasyEDA is one shared resource** → a claim per session, automatic on first access, expiring after 15 minutes;
   short runs may be let in between two long ones and EasyEDA comes back afterwards. Several sessions at once were
   normal – one routes, one writes docs, one researches a part. A second session's run pulled the tab away: a
   20-minute routing run was lost that way, and writes can land in the wrong document. A part lookup once waited
   38 minutes behind a layout session, and the 7-minute connector swap above waited 93 minutes before the claim
   existed.
2. **Clicks** → avoid them through the API (parts and nets without the dialog); release EasyEDA while waiting for a
   click; ask for it when someone is at the keyboard; the click is a plain OK. A session once held EasyEDA for
   49 minutes for a click nobody knew about, running a DRC every minute.
3. **Wait loops with `pgrep -f`** found their own shell and never ended – six times, ten minutes each, and one aborted
   run went unnoticed for 11 minutes → wait for an end line or the PID.
4. **Library footprints cannot be repaired through the API** → change the graph (which pad gets which net) and let
   everything follow.
5. **Regenerating a big schematic costs ~9 minutes per change** → only the board schematic is rebuilt for layout
   changes; parts sync in place.
6. **A generated schematic drifted** (a pin on two nets) without anyone writing to it; regenerating fixed it → the
   reference schematic is checked at the start of every EasyEDA session and before every gate run. The cause, found
   on pytree (#117): EasyEDA lists a pin of the saved schematic, opened again, on a second net; a tab left open showed
   the drawing → the check reads the saved state, always (6.2).
7. **Checks missing in the flow** (the hardware tests did not run after a graph change; CI found it) → the pre-commit
   hook runs the fast hardware tests whenever hardware files are staged.
8. **Small things with consequences:** API connection errors that stalled a session until someone typed "continue";
   a gate stage that did not wait for the bridge; `tail -3 a b` failing with a newer coreutils; output filtered so
   hard that an abort was invisible.

## 13.3 What we would do again

- **The graph as the only source.** Every change was a few lines of JSON plus a pipeline run. A redesign of the power
  concept took a day.
- **Checks at every hand-over, the last one on the Gerber files.** The copper connectivity check from the Gerber
  export never trusted EasyEDA and caught what the DRC could not explain.
- **Freerouting with our own DSN.** Deterministic, offline, checkable before anything is written. Reshuffling the
  order on failure solved what looked like unroutable nets: after one part was recreated – it moved to the end of
  EasyEDA's list – one GND link stayed open three times in a row with the same plan.
- **Independent agents for the judgement calls**, and their result as the sign-off. The second datasheet check found
  a footprint with "+" at the cathode and two holes too small for their leads; the layout review found the 61-mm
  switching loop. All three would have hit every board.
- **Numbered decisions** with reasons in the words of the person who decided. Sessions days later knew why a track is
  thinner than its class and that it was accepted.
- **Fix the cause, not the symptom.** Throttling, the bridge timeout, the return depth – each took an hour to find
  and removed a whole family of failures.

## 13.4 What we would do differently

- **Freerouting from day one.** A day went into EasyEDA's autorouter and into repairing its leftovers (GND islands,
  ripped-up nets, GND-first routing). None of it survived: a failed run kept no track (1773 lines → 223), and the
  repairs converged nowhere.
- **The layout review as a gate condition from the first release**, not after the first released run.
- **The EasyEDA claim before the second parallel session**, not after a lost 20-minute run.
- **Tooling holes and the assembly type (Economic vs Standard) in the first layout**, not after the first quote – they
  constrain where parts can go, and pytree found them only in the quote.
- **Check the target before writing.** On the second project `createProject` silently returned null and the first
  generated schematic landed in pytree (removed a minute later). Every write path now starts with "is the open project
  the configured one?".
- **Generic from the start.** The scripts began full of project constants (outline formula, LED channels, decoration).
  This repository is the generic extraction; a new project starts with an edakit.toml instead of a copy of scripts.
  The project went on growing after the extraction (0 Ω bridges, a common-anode star LED, pour-only nets). Before it
  can use edakit, those have to come back – one feature proposal each, which is why the proposals of chapter 11 exist.

## 13.5 Numbers

- 7 days from the first MCP call to a redesigned, routed board; first released manufacturing files after 5 days, from
  the first graph on 19 October to the release on 23 October.
- ~120 parts, 98 nets; routing ~1500 track pieces, ~220 vias, DRC 0.
- Simulation: 41 scenarios, ~11 000 single checks in about 3 seconds.
- Release gate: 7 stages, about 30 automatic checks in the board and manufacturing stages alone, 5 manual checks of
  which 2 are done by agents before the export.
- About 60 EasyEDA API behaviours that cost time to find out (chapter 9).

## 13.6 The second project

The first project after the extraction was much smaller:
[the Christmas bell](https://github.com/tgd1975/automatic_christmas_bell), a carrier board for a plugged-in Arduino
Nano with a servo, five LEDs and two buttons, taken over from a Fritzing drawing. The circuit itself was quick: graph,
parts and simulation took under an hour. Most of the time went into what the bell exposed in edakit, which had to be
built before the board could go through:

- **Off-board loads** in the simulation (`external`: the servo at its connector) and **fault cases** that do not block
  every commit (`"matrix": false`): a stalled servo draws more than the Nano's 500 mA polyfuse holds.
- **5 V I/O modules** (`v_io_v = "vin"`) and an **input level check**: the buttons switched 3.3 V into a 5 V AVR,
  0.28 V above its VIH – visible now, and moved to 5 V.
- **Pin names** are compared with the symbol: it caught three LED entries whose names disagreed with their symbols –
  one library series marks the anode with "+" on pad 1 for green and red and on pad 2 for yellow.
- **LEDs side by side point the same way** (plan check), after the first silkscreen showed the yellow ones turned.
- **A new project's default board** is adopted, and **project creation is manual** in the local desktop client
  (chapter 9.2) – with a guard after the first generated schematic landed in the wrong project.
- The gate's hole check (GEO.hole) failed the Nano footprint from a user library: 0.9 mm holes for 0.64 mm square header
  tails. Library footprints are not checked by anyone else.
- **Publishing what is ordered** was a script of the bell's own first: it published its four boards – the main board
  and the variants smd, tht and esp32, twelve order files – as a draft with it, before `edakit release publish`
  (chapter 8.3) took it over.

## 13.7 After the first board, day by day

The dates that stood in the other chapters, from pytree's DRC rule set to the first carts at the makers. Each row
stood with its date in the chapter of the last column, which keeps the statement without the day.

| Day | What happened | Chapter |
|---|---|---|
| 22 Oct | The DRC rule set read on EasyEDA Pro 3.2.206 from pytree (`tests/fixtures/easyeda/drc_rules_3.2.206.json`) | 9.4 |
| 26 Oct | The bell: `SCH_PrimitivePin.modify` is not saved – the last of the API behaviours found between 19 and 26 October | 9.4 |
| 30 Oct | The bell reported EasyEDA's BOM tool mixing tabs | 9.2 |
| 30 Oct | Decided: nothing orders or pays; the fee table takes what maps one to one from an order at once (ordering step 5) | 8.4 |
| 31 Oct | The parts library written from the datasheets: six parts whose EasyEDA symbol differs from the manufacturer's datasheet | 4.4 |
| 31 Oct | `dc_bias` of class-2 ceramics: KEMET's and YAGEO's part sheets (search.kemet.com) carry it; Samsung's, Murata's and TDK's could not be read for the library | 4.1 |
| 31 Oct | Decided: PARTS.library notes a copy whose library entry changed (grade `newer`) and a copy of an unsigned entry (grade `draft`) – rules-at-scale.md, decision 8 | 4.1 |
| 31 Oct | Live run of 3.6: EasyEDA could not place a rebuilt copy ("Cannot convert undefined or null to object") while the schematic's parts still carried the carrier – since then `schematic create --save` and `schematic layout --save` come before `pcb parts`; the pads of a footprint in the project come back as built | 4.5, 9.4 |
| 31 Oct | KiCad live test LT-10: a first schematic create in a new project left the template named after its page and a panel named `generated_main` (`keep_schematic_name` in `edakit/eda.py`) | 6.1 |
| 31 Oct | Renaming answered false, then true without effect, in every project, after hours of runs, until EasyEDA was restarted | 9.3 |
| 31 Oct | The DRC rule set written live (step 2.2): what is written holds after save and reload | 9.4 |
| 31 Oct | A comparison of stage E whose finding is a warning no longer fails the gate; before, every comparison that did not hold failed it, whatever its finding's severity (walkthrough-gaps.md) | 8.3 |
| 31 Oct | Decided: a footprint has no regulatory content (the electrical hash); on a board with `[looks]` the order's `mark` is `"remove"` (also in the comment of `edakit/config.py`) | 8.2, 8.4, 10.2 |
| 1 Nov | The live check on EasyEDA Pro 3.2.209: the sentences of chapter 9 that start "3.2.209:", among them that `modifySchematicName` and `modifySchematicPageName` look the UUID up in the project tree | 9 |
| 1 Nov | ODB++ export live (ordering step 0b, EasyEDA Pro 3.2.206, a probe board) | 9.1 |
| 1 Nov | TD-37 live: a resistor placed through the API – the old way the Import Changes item, the new one none | 9.4 |
| 1 Nov | On a PCB never reloaded since EasyEDA's start, pours refilled and tooling holes replaced, the DRC reports 0 | 9.4 |
| 1 Nov | Pours: easyeda-mcp-pro 1.6.0 and EasyEDA's beta `rebuildCopperRegion`; edakit's pour follows the outline (E-13, live) | 9.4 |
| 1 Nov | Ordering step 0 recorded the four forms in our accounts (`recorded` in each profile), and the skill cart ran live at every maker up to the cart, nothing ordered – on a copy of the example blinker-555 released on the KiCad tool chain (`tests/fixtures/makers/LIVE.md`: 5.7 JLCPCB, 5.12 PCBWay, 5.8 Eurocircuits, 5.10 AISLER up to its price) | 8.4 |
| 1 Nov | Decided: the wishes to the makers stay future work | 8.4 |
| 2 Nov | The first order: pytree's tree, five assembled, from the JLCPCB cart the skill cart filled and checked (the cart record of run 20261101-225744), and the bell's variants tht and esp32tht, five bare each, in the same order – the bare boards without the cart's protocol, since edakit's cart takes bare JLCPCB boards only from 0.4.17; the LCSC parts in one shipment with it. With it edakit 1.0.0 | 8.4 |

## 13.8 How the chapters' details came about

The rules of edakit are lessons. Along the way the checks on pytree found a library footprint with "+" printed at the
cathode pad, fixed by swapping the nets in the graph. They found holes too tight for the leads of two parts, a pin of
the generated schematic that had drifted onto two nets, and a 61-mm detour in a switching regulator's current loop.
Late, the layout review agent found that the gate had released a run without anyone reviewing the layout. Each became
a check, as did the bell's holes too small for header tails.

### The approach and the graph (chapters 1 and 3)

- The failures chapter 1 lists under "Why not just draw it in EasyEDA?" all happened or nearly happened in pytree, and
  each one was caught by a comparison against the graph, not by looking.
- `hardware/graph.json` was the form every project had until October 2026; chapter 3 calls JSON the older form, kept
  until a project converts.
- Only roles decide which pin is a cathode (the firmware contract, 3.5) because an exporter of pytree once found a
  cathode by the name "K" and nearly wrote a wrong channel table.

### Parts, schematic, PCB (chapters 4, 6 and 7)

- The query of `edakit part search` in 4.2 lists the Kingbright C6751358 and the XINGLIGHT C7371894, which took pytree
  some 30 searches in EasyEDA's search.
- The LED footprint of 4.4: EasyEDA's footprint of a 5-mm LED printed "+" next to pad 1, while symbol and datasheet
  called pad 1 the cathode. Editing the project's footprint through the API went nowhere – the two dead ends of 13.2.
  The fix was in the graph: the anode's net goes to the pad with the "+" print, and the parts entry gives pin 1 the
  role `anode`, so every check, the simulation and the firmware pin tables follow.
- The build of own footprints (4.5) runs EasyEDA calls the bell's and pytree's scripts use.
- An empty netlist is read ten times before a schematic is saved (6.1) because EasyEDA returned one after many writes
  in pytree, and the script saved it.
- `DMT_Schematic.copySchematic` (6.3) once copied another project's schematic onto the template – the bell's ESP32 THT
  template, 19 parts for a graph of 17. Since then such a copy is deleted where it is a free schematic of the open
  project, and the run names what EasyEDA made – its page, the company and graph version of its title block, the parts
  more and missing – and exits 1.
- The part diff of 7.3 shows pytree's slide switch (XUNPU SS-12D11G9 for G-Switch SS-12D11-G090): turned 180°, the
  mirror image fits equally (symmetric), map 1→3, 2→2, 3→1, 4→4, 5→5, pitch 4.70 → 4.80 mm, the 0.40 mm tab slots
  below 0.5 mm, `SW5: BAT_SW 1 → 3`. By hand it took an hour with both datasheet drawings, and it was first described
  as a turn when it is a mirror image.
- `pcb dump` wrote the footprint geometry among the artifacts until October 2026
  (`<artifacts>/pcb_geometry_<board>.json`, not versioned); it now lies beside the board file (7.4).
- Freerouting's plane (7.5): with the ground net as the plane, 70 of 178 connections stayed open – hence the net whose
  pads are spread over the side.
- Reload when the DRC asks (7.5): right after API changes the DRC once reported 320 false connection errors; saved and
  reloaded, 0.
- The Import Changes item (7.5) alone held pytree's gate at GEO.drc in ten runs, once for 2¾ h while the first
  diagnosis was wrong.

### The release gate (chapter 8)

- **M-5, the layout review.** pytree's first released run had passed every automatic check, and nobody had looked at
  the layout as a whole. The layout review agent then found a switching regulator loop routed across the whole board
  (now GEO.loop) and a visible side crowded with tracks. Since then the review is a condition of the release, not a
  tool you may use – in the gate's own list, so that a project whose sign-off file never had it is held to it too. It
  ends every layout round that changed placement, routing or pours (skill pcb-round), on the round's Gerber export, so
  its findings come before the gate rather than after it.
- **GEO.pour.** Later in the same project a run was released with about 45 % of one side bare: EasyEDA had dropped
  pour islands without a pad, and gate, DRC and layout review all passed it, because none of their inputs showed the
  copper as filled.
- **The looks row of stage L** has the numbers in the protocol: pytree's layout review measured the LED side by hand
  at every round.
- **The one-file edakit.toml** lasted until October 2026; a project that moved from it records the hashes before and
  after in `rehashed` of its sign-off file (8.2).

### The EasyEDA API (chapter 9)

Chapter 9's behaviours were found by trial on EasyEDA Pro 3.2.206 (Linux) with easyeda-mcp-pro 1.4.0, between 19 and
26 October 2026. A sentence starting "3.2.209:" is what the live check on EasyEDA Pro 3.2.209 found on
1 November 2026, each call checked against the JSDoc of the client's types first (`upstream/README.md`).

### Working with Claude Code (chapter 11)

- The plugin and the working agreements came out of a week of daily use.
- The project agents with `replaces` have pytree's as their example: elektrotechniker for M-1, pcb-pruefer for M-5
  and its round reviews. pcb-pruefer reviews the rounds and signs M-5 in place of the edakit reviewer (the roles of
  14.1).
- The project used a small coordination tool with a commit lock, an active branch and a log book, enforced by a
  PreToolUse hook on git commands; chapter 11 recommends such a tool for parallel sessions.
- The agreements of 11.4 reach every session through the plugin, so a new project does not learn them again by trial.

### Design, KiCad and the walkthrough (chapters 14, 16 and 17)

- REQ.missing (flyback diode) and REQ.missing:cc (USB-C termination) are pytree's buzzer stage and USB-C input turned
  into rules.
- KiCad's DRC with schematic parity (16.8): the first run found every pad in conflict with the schematic, since local
  labels name a net "/GND"; the schematic has global labels since.
- `route all` on KiCad (16.8): two things had to be learnt when `pcb apply` and `silk apply` wrote the file KiCad had
  saved again – KiCad 10 names nets in items by name, and leaves out `(filled_areas_thickness no)`, which under
  KiCad 8's version gives a fill a stroke of `min_thickness`. Then the DRC found nothing again.
- The coin-cell walkthrough's sign-offs (17.9): a day after the first ones edakit renamed its checks into codes, and
  `edakit convert --write` turned `waive` and `hints` into `accept` and `ratings` into `limits` with the unit in every
  name. The circuit hash changed, both agents looked again – the same values, the same simulation – and M-1 found a
  hint that repeated PATH.reverse (13.9).
- The same day the hash changed twice more. First the accept of HINT.debounce left the graph and the cell's current
  limit came in (17.6, D-7); M-1 checked the new accept's reason against the cell's data sheet. Then BT1's entry got
  the outline of holder and cell (`body.box`). Both agents signed each new hash.

## 13.9 What the coin-cell walkthrough changed in edakit

Like the Christmas bell (13.6), the coin-cell board of the walkthrough (chapter 17) found gaps on its way, and each
one was closed in edakit:

- **`edakit part fetch` before the graph.** It failed with a traceback while the project had no graph yet; it reads only
  the parts database now.
- **A certificate kept as the datasheet.** LCSC's datasheet address now answers with a page of the shop whose only PDFs
  are the certificates in its footer; `part fetch` took the first link and kept LCSC's ISO 9001 certificate as the
  holder's datasheet. A page is now followed only to where it sends the browser, to its viewer or to a link that names
  the part or says datasheet, and LCSC's page is taken as the file behind it (datasheets, 4.6).
- **A push button stopped PATH.reverse and PATH.unfed.** A switch passes a reversed source on, and a supply; a push
  button passed neither, so PATH.reverse named SW1 itself and a supply behind a power button counted as unfed. A push
  button passes both now, as a switch does; the Christmas bell's results did not change.
- **The push button of the block library** called pins 2 and 4 `B (internal to A)` and `D (internal to C)`, its symbol
  `B` and `D`: STRUCT.entry failed as soon as `part import` had cached the symbol. The names follow the symbol now, and
  the notes and roles say that the pins are connected inside.
- **A polarity hint for a holder PATH.reverse had checked.** HINT.input_polarity said that nothing checks the polarity
  of a battery holder not marked reversible – but PATH.reverse starts from every holder by its kind. The electrical
  reviewer found it in M-1; the hint names unmarked supply connectors only now (JST packs, barrel jacks).
- **A round board had four points twice.** Each of the circle's four arcs began where the one before ended: four
  segments of length 0 in the outline EasyEDA and Freerouting got. The outline now drops a point equal to the one
  before.
- **The drawings of this chapter on the documentation site** linked to GitHub's page of the file, which is no image; the
  site carries the images now.
- `edakit order` said "1 parts by hand", and `edakit block add` still sent you to `edakit hints`, which had gone with
  the codes.

## 13.10 What the 555 blinker changed in edakit

The 555 blinker of walkthrough 2 (chapter 18) – the first real board through the KiCad tool chain, and the first on
cells behind a power switch – found these gaps; each was closed in edakit with its test:

- **A load's budget on a battery holder.** `expect` in a load named sources and nets only; `{"BT1": {"i_max_a": …}}`
  was SIM.config. It holds the current from the holder's cells now (LIM.i) – R-3's 1 µA and R-4's budget.
- **A part switched off.** LIM.range held U1 at 0 V with SW1 open to its 1.5 V minimum. A supply within 0.5 V of
  ground – where the model's own loads are off too – is a row of information, "unpowered"; a part at 1.0 V is still
  below its range, and one at −0.9 V reversed.
- **An LED on an open-drain output.** LVL.undefined/open_drain wanted a pull-up on LED_K. A net that holds nothing but
  the outputs and LED cathodes is their load; nothing reads it.
- **A floating node behind a blocking MOSFET** (cells upside down, 18.6). The behaviour `logic` has a substrate diode
  from its ground to each supply pin; with the cells reversed and nothing to block them it carries the amps a real IC
  would.
- **A cell upside down delivered "charging" current.** A cell state below 0 V is counted in its own sense now.
- **The library footprint's box.** EasyEDA's BBox of the SOIC-8 of C90760 ends at 126 mil while its pads reach
  137.8 mil: the box `part import` caches covers every pad now.
- **KiCad's nets of no-connect pins.** KiCad nets a pin its schematic marks no-connect as "unconnected-(SW1-Pad3)",
  and its parity check wanted those nets on the pads. `pcb apply` takes them from KiCad's netlist export; read back
  they are no net, as the graph has it.
- **A body as large as its footprint.** BT1's `body.box` from the drawing (53.00 mm) and its library box (53.04 mm)
  differ by a rounding, and the footprint's own outline on the edge was a GEO.silk warning. 0.05 mm are rounding now.
- **One output resistance for every corner.** U1's discharge pin at its 1.5 V maximum hid R-4's real current (the
  reviews, 18.8); `r_out_ohm` takes a range now.
- **A tooling hole under a part fitted by hand.** `pcb plan` held BT1 to the keep-out of a tooling hole; a part with
  `bom: false` is not there while the tooling holes hold the board.
- **Thermal spokes on KiCad.** KiCad's DRC wants two by default, where Freerouting left two GND pads room for one
  (the layout, 18.11). The KiCad project edakit writes asks for one: EasyEDA asks for none, and GEO.copper checks the
  connection.
- **A square notch around each tooling hole.** The pours on KiCad kept the notch to the edge EasyEDA once needed (M-5,
  note 7). The pour follows the outline now, and a rule area keeps each hole's keep circle free – KiCad fills up to it.
- **An LED's ideality of 2.** D1's datasheet curve lay 20–25 mV above the model at 0.5 mA (M-1). `values.vf_vs_if`,
  points read off the curve, sets the ideality now; without it the model stays as it was.
