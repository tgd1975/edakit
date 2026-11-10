# EMC in the layout: fast nets, long tracks, return paths, supply entry, crystals, USB data, cables

Status 2026-11-10: decided, nothing built. The decisions were taken by the owner the same day in a decision round in
Claude Code's form (Decisions, at the end): all seven steps, in three branches. A plan for the test firmware was added
the same day as EMC.8, on the owner's word, in a fourth branch. The building starts on the owner's word ("umsetzen").
Asked for by the owner: whether edakit's rules cover EMC best
practice, and how likely pytree is to run into trouble because of its longer tracks. A first version listed six gaps
("ja. was ist mit den anderen punkten?"). The owner then asked for a review of it: "review emc-layout .... sind alle
regeln belegt? sind alle regeln im kontext von edakit sinnvoll und umsetzbar?" and "auch anhand von den anderen
projekten überprüfen (glocke, pedal)".

This version is the result of that review, the same day. Every rule now rests on a source that was read; the review's
findings and what they changed are listed at the end. Written against main at `77ee7cb0`.

The reviewed version then deferred three steps "until the first project that needs it", at "2–3 days" for GEO.return.
The owner rejected that reasoning: "und dann braucht das das projekt sofort und wir haben keine tage zeit für die
umsetzung ... reden wir hier von deiner zeit? warum so lange?". Nothing is deferred now. The sizes are session time,
measured against how long a comparable check took here (the table of steps, below).

This concept supports layout and covers technical risk only. It is not legal advice, guarantees nothing legally and
makes no claim to be correct. Whether a board meets EMVG § 6 or 2014/30/EU stays with the regulatory review (M-6,
handbook 15).

## The short answer

edakit checks EMC today where a project once got it wrong:

- GEO.loop: the switching loop of a regulator, if it is listed;
- HINT.switcher, HINT.esd, HINT.inductive;
- HINT.cable_line, which already asks for a series resistor on an output that runs through a cable and a return wire
  beside a clock;
- the decoupling capacitor next to each IC (SYNC.plan);
- the nets kept apart (`layout.apart`, GEO.spacing).

What it lacks is the layout of the signals with fast edges. TI's guide for two-layer boards, SZZA009, gives three rules
with numbers:

1. **Only some nets matter.** Signals whose edges come at more than 50 kHz cause the emissions. Slower ones, PWM at a
   few kHz included, are no EMI concern.
2. **Long fast tracks.** On an unshielded two-layer consumer board, such a track longer than 4 inches (101.6 mm) can be
   a problem in the FM band. It wants termination, a series resistor at the driver being the preferred kind.
3. **Ground under fast tracks.** Their return should run directly under them, and the ground should be gridded.

The review found that the first version did not hold up in three places:

- It would have checked every MCU output and every PWM net. That is too broad: on the bell it would have flagged LED
  and servo lines that SZZA009 calls harmless.
- It rested on an edge time from the datasheet. The datasheets of all three MCUs in the projects (RP2350, ESP32,
  ATmega328P) give none.
- It selected fast nets by `clock_hz` and `fn`. No project's graph sets these, pytree included.

The steps, all decided (Decisions, 1):

| Step | What | Source | Hits in the projects today | Size (session time) |
| --- | --- | --- | --- | --- |
| EMC.1 | Fast nets: which nets count, and a coverage line when edakit cannot tell | SZZA009 1.3, 2.6.3 | pytree: the SPI chain | about 1 h |
| EMC.2 | GEO.length: a fast net longer than 101.6 mm from its driver without a series resistor next to the driver | SZZA009 2.4.2, 2.4.3, 2.2.5 | pytree: TLC_CLK 126.5 mm, TLC_SDO 118.4 mm | about 2 h |
| EMC.3 | Questions for the layout review (M-5) in the core domain: ground under fast tracks, gridding, fast tracks at the board edge, Freerouting and fast nets, crystals | SZZA009 2.1–2.6, SCAA082A 1.6, SPRAAR7J 2 | every board with fast nets | about ½ h |
| EMC.4 | HINT.supply_entry: a small capacitor at the supply entry of a board with fast nets, a place for a ferrite | SZZA009 2.2.4, 2.5.4, 2.5.5, 3.3, 4 | pytree: J1 | about 1 h |
| EMC.5 | GEO.return: the reference copper under every fast track on the Gerber raster | SZZA009 2.1.2, 2.1.4, 2.2.3; SCAA082A 1.6; SPRAAR7J 2 | pytree: V_LED without a capacitor to GND near U3–U5 | 3–5 h |
| EMC.6 | HINT.crystal: a crystal on the board, its place and its neighbours | SZZA009 2.4.1, 2.1.3; Raspberry Pi, Hardware design with RP2350, 4 | none: every crystal sits on a module | about 1 h |
| EMC.7 | domain usb: the routed USB pair | Raspberry Pi, Hardware design with RP2350, 5.1; SPRAAR7J 1.2 | none: USB plugs into a module everywhere | 1–2 h |
| EMC.8 | `edakit firmware emc`: a plan for the test firmware of an EMC measurement, from the circuit | the firmware contract (handbook 3.5), EMC.1 | pytree: the chain shifting with its read-back, 24 channels, DIP mirrored | 1–2 h |

Together that is about two working days of session time, in four branches (EMC.1–EMC.4, EMC.5, EMC.6 with EMC.7, EMC.8).
Each branch goes onto main with the owner's OK, as a `patch` version. The sizes are measured against proposal #103, a
check of the same kind on the same Gerber raster (GEO.pour's bare area per side): from the issue at 11:45 to the merge
of #138 at 15:28 on 2026-11-01, triage, tests, catalog and handbook included. The steps without hits today are tested on
synthetic Gerber files, as `tests/test_fab.py` writes them. A live run on a published design with a crystal and a USB
pair on two layers is possible too: Raspberry Pi's RP2350A Minimal KiCad design, through edakit's KiCad toolchain, which
writes `pcb.json` and Gerber files from a KiCad board (`edakit/toolchain/kicad/fab.py`). Its licence is checked before
anything of it goes into the repository.

Dropped: the edge time as a part fact (no datasheet gives it), and the note on long inputs with an internal pull-up (no
source asks for a length limit).

All steps read what is text already: the graph, the part entries, the board file, `pcb.json` and the Gerber files.
They leave nothing that exists only in EasyEDA or in someone's head.

## The projects

| Project | Board | Nets above 50 kHz | What the proposed rules would report |
| --- | --- | --- | --- |
| pytree | tree, two layers, RP2350-Zero module; tracks on TOP (pytree's "hinten"), V_LED poured on BOTTOM | the SPI chain to U3–U5: TLC_CLK (1 MHz, `firmware/leds.py`), TLC_SDI, TLC_SDO. LE pulses once per update, and OE, the star and the buzzer switch at 0.5–2 kHz. All of these are below 50 kHz. | EMC.2: TLC_CLK 126.5 mm to U3 and TLC_SDO 118.4 mm from U3, no series resistor (TLC_SDI 92.3 mm passes). EMC.4: J1. EMC.5: no capacitor between V_LED and GND near U3–U5 (only C1 and C4, in the foot). |
| bell (automatic_christmas_bell, all variants: Nano, ESP32, THT, SMD) | main, two layers, Arduino Nano or ESP32 module | none: servo at 50 Hz, LEDs, two buttons with 4.7 kΩ pull-downs | nothing. The first version would have flagged SERVO (66.3 mm) and the button lines (96–109 mm). |
| desk-led | main, battery, switch, LED | none, no MCU | nothing |
| pedal (AwesomeStudioPedal) | no PCB and no edakit project: NodeMCU-32S on wires, five footswitches with 10 kΩ pull-ups and LEDs on 30 cm and more of cable (maker-coverage) | none: footswitches and LEDs are static or slow | Only the cable rules apply. HINT.cable_line and HINT.esd exist; SZZA009 2.5.3 adds the ratio of return wires (EMC.3, cable question). The radio (BLE) is the domain radio's. |

The lengths are measured on the released runs: pytree `20261101-225744`, bell `20261101-142527`. They are the shortest
path over tracks from the MCU's pad to each load's pad, computed by `loop_length_mm` of `edakit/release/fab.py`.

Only one bus on one board is a target today. That is no reason to wait. A check has to be in place before the board
that needs it is ordered, or it comes too late by construction. GEO.pour came the other way round: pytree's bare back
was seen by eye the evening before the order (GEO.pour, why).

## EMC.1 Fast nets

**Rule.** A net counts as fast when its edges come at more than 50 kHz. SZZA009 1.3: "only worry about signals that make
an edge transition at a rate greater than 50 kHz"; 2.6.3: "Only signals with switching rates below 50 kHz can be left
safely to the autorouter." A pin that changes at most once per 100 instructions is no concern either (1.3). That leaves
out a latch pulsed once per update and PWM at a few kHz.

**Data.** In this order:

1. `clock_hz` on a clock net (`fn: "spi.sck"`, I2C SCL), with the data lines of the same bus (`fn_bus`); `pwm_hz` above
   50 kHz.
2. **Without them**, a clock edakit finds by roles: the clock of a chain (`chains.common` of the firmware contract,
   3.5) or of a bus whose devices have an SPI or I2C clock pin. Its frequency is unknown. *Recommendation:* it counts as
   fast. SZZA009 1.3 names the clock as the noisy pin, and nobody runs a shift register's clock below 50 kHz on
   purpose. The data lines of that chain or bus count with it. Latch and enable lines count only with `pwm_hz` or
   `clock_hz` above 50 kHz.
3. A line `fast nets: …` in `edakit check --coverage` lists what counted and why, and the clocks that counted without
   a frequency, so a project can set `clock_hz` and be sure.

pytree's graph sets none of these fields. With step 2 its chain counts: TLC_CLK, TLC_SDI and TLC_SDO.

## EMC.2 GEO.length – long fast tracks

**Rule.** For each fast net, the path over tracks from the driving pin to each load. A **warning** when a path is longer
than 101.6 mm (4 inches) and no resistor sits in series next to the driver.

- SZZA009 2.4.2: "For automotive and consumer two-layer boards, 1/50 of the wavelength begins to be critical,
  particularly in unshielded applications. That says traces longer than 4 inches can be a problem for FM-band noise. In
  these cases, some form of termination is recommended to prevent ringing."
- SZZA009 2.4.3: series resistance "is the preferred method for microcomputer-based systems". Termination is also
  needed for a trace over 1 foot and a signal to a cable that leaves the enclosure; HINT.cable_line covers the cable.
- SZZA009 2.2.5: 50–100 Ω in series with an output, "as close as possible to the microcomputer".

SZZA009 sets its noise limit stricter than FCC Part 15 (abstract), so the rule is conservative for a consumer board.

**Next to the driver** is the one number without a source: a resistor whose pad lies within 10 mm of the driver's pin,
and nothing else on the net between them. It is open to change when a source gives one.

**Fix** (the warning says it):

- a 50–100 Ω resistor at the driver, a 0603 on the board;
- on a board already made, slower edges and a lower frequency in the firmware. SZZA009 1.5 and 2.5.1: rise and fall
  times "reduced to the maximum (slowest) allowable", the signal "at only the minimum needed frequency".

On the RP2350 the slow slew is the reset value already (pad register `SLEWFAST`, reset 0 = slow). The drive goes from
4 mA, the reset value of `DRIVE`, down to 2 mA (RP2350 datasheet 9.6). An accepted warning names what was done.

**Data.**

- The path comes from `pcb.json`, as GEO.loop measures it, with one extension the measurement showed: `loop_length_mm`
  knows pads only at both ends. A net that runs through a pad is open for it; pytree's TLC_CLK reaches U5 that way, and
  the path from U1 came back as none. Pads, and vias from the drill file, become nodes of the path graph.
- The driver is the pin of the MCU, or for a read-back line like TLC_SDO the `sdo` pin of the chain. The series
  resistor is a part of kind resistor between the driver's net and the track.

**No edge time.** The first version wanted the edge time `t_edge_ns` from the datasheet as a part fact. None of the three
MCUs of the projects gives one:

- the RP2350 datasheet: drive 2–12 mA and slew slow or fast, no times;
- the ESP32 datasheet: none;
- the ATmega328P datasheet: none.
The 4-inch rule needs no edge time, so the fact is dropped.

**pytree.** Warnings for TLC_CLK (126.5 mm to U3) and TLC_SDO (118.4 mm from U3 to the module). In practice the chain
test at start (pytree's D-22) would show a doubled clock. For the boards built, the remedy is the drive of GP26 and of
U3's SDO side. U3's drive is not adjustable, so it stays a warning to accept.

## EMC.3 Questions for the layout review (core domain, `[review] pcb`)

Some advice in the sources has no number edakit could check, or would hit every board. It goes into the questions the
agent pcb-reviewer asks at M-5, next to the existing ones on exposed pads and antennas. The questions are text, are
read on every board, and cost nothing to run:

| Question | Source |
| --- | --- |
| Ground under fast tracks: does each fast net's return run directly under it, on the other layer or in a ground track beside it? Is the ground gridded – fills tied to ground at two or more points, vias where top and bottom ground cross, "as many through holes as can physically fit"? | SZZA009 2.1.2, 2.1.4, 2.2.3 |
| Slots and splits: does a fast track cross a gap in its reference copper – a slot, a split between two ground nets joined by a 0 Ω bridge, a supply pour? Then a bridge or a capacitor (1 µF or less) across the gap, next to the crossing; a change of the reference ground net with stitching vias within 5.08 mm (200 mils). | SCAA082A 1.6 (a 0 Ω resistor over the slot); SPRAAR7J 2 (written for high-speed interfaces, so strict for an MCU board) |
| A supply pour as reference: where fast tracks run over a poured supply, is there a capacitor between that supply and ground next to the receiving IC, so the return can cross? | SZZA009 2.2.4, SPRAAR7J 2 |
| Board edge: does a fast track run along the edge of the board, where its return has copper on one side only? "Never run noisy traces on the outside edge of the board." | SZZA009 2.4.1 |
| Freerouting: were the fast nets routed by plan (fixed wires, `route all` with the routes first) or left to the autorouter? | SZZA009 2.6.3 |
| Crystal on the board: no unrelated part within 25 mm (1 inch); load capacitors and ground right at the crystal and the MCU, the tracks as short as possible. | SZZA009 2.4.1, 2.1.3; Raspberry Pi, Hardware design with RP2350, 4 |
| Cables: one return wire per signal as a twisted pair is best; never fewer than one per nine signals; over 1 foot of cable, one per four. | SZZA009 2.5.3 |

Not proposed as a question or check: **3:1 length to width** for power and ground tracks between an IC and its source
(SZZA009 2.1.1). Every module-fed board misses it (pytree's 3V3: 0.3 mm wide, 96 mm of track), and on edakit's boards
the pours do that job (GEO.pour). Also not proposed: **series resistors on every I/O pin** (SZZA009 2.2.5). The source
itself says these "are not well accepted in production". It ranks lines leaving the enclosure first, and HINT.cable_line
asks for those.

## EMC.4 HINT.supply_entry

**Rule.** A board with fast nets (EMC.1) and a supply input gets a note:

- a ceramic capacitor below 1000 pF (about 470 pF) from each supply wire to ground, right at the connector, beside the
  bulk capacitor;
- the ground of that capacitor wide, at most 3:1 in length to width;
- a place for a ferrite bead in the supply line, on the supply side only, never in ground. A measured problem then
  becomes a part change, not a new board.

SZZA009 2.5.4, 2.5.5 and 3.3 give the capacitor for every wire that enters or leaves the enclosure, below 1000 pF so
that its ESR is lowest at 50–500 MHz. 2.2.4 gives the ferrite on +V only. Its summary (4) gives "filtering of critical
lines, such as the supply line, ensures that high-frequency currents do not leave the PCB". SZZA009 ties that capacitor
to a metal enclosure's shield; in a plastic or printed enclosure it goes to the board's ground at the connector.

**Data.** The matcher `power_input` of `engines/hint.py` finds battery holders, connectors with a `vbus` pin, reverse
protection and simulation sources. With the condition "fast nets on the board", the bell and desk-led stay silent.

**pytree.** J1, if its part entry gives the pin role `vbus`; otherwise the matcher misses it, and the coverage line says
so.

## EMC.5 GEO.return – the reference under fast tracks

The check behind the EMC.3 questions on slots, splits and supply pours, on the Gerber raster.

**Rule.** For every track of a fast net (EMC.1), the reference copper under it on the other layer: a ground net, or a
supply poured there. A **warning** for each of these:

- **A gap** in that copper (a slot, the edge of a pour) whose two sides are not joined within 5.08 mm of the crossing.
  They are joined by a via, a 0 Ω bridge, or a capacitor of 1 µF or less between two reference nets.
  - SCAA082A 1.6: a 0 Ω resistor over the slot.
  - SPRAAR7J 2: stitching capacitors of "1 µF or lower and placed as close as possible to the plane crossing", and
    stitching vias "within 200 mils".
- **A supply as the reference** with no capacitor between it and the receiving part's ground within 5.08 mm of the
  part. The return cannot cross to the part's ground there.
- **A ground fill under the track tied at one point only.** SZZA009 2.2.3: "A ground-fill-pattern geometry connected at
  only one point is just a ground shield".

The 5.08 mm are SPRAAR7J's 200 mils for stitching vias. They are used for the capacitors as well, where the source says
only "as close as possible". SPRAAR7J is written for high-speed interfaces, so the distance is strict for an MCU board.

**How.**

- The reference copper is GEO.copper's raster (`gerber.Copper`): `net_mask` of the ground nets, and of the supplies
  poured on that layer.
- Along each track, every 0.5 mm, the band under it as wide as the track. A run of samples without reference copper is
  a gap.
- For a gap: `ndimage.label` of the reference copper inside a disc of 5.08 mm around it, on both layers. The copper is
  joined through the vias, and through the bridges and capacitors whose pads lie in the disc. Copper before and after
  the gap in one component counts as joined.
- That is the labelling GEO.copper does already, on a window; a global detour path is not needed.
- The tie points of a fill are its pads and vias, counted by the union of islands that GEO.copper keeps.

**pytree.** Its tracks lie on TOP, and BOTTOM is V_LED: a supply as the reference. U3–U5 have no capacitor between
V_LED and GND, so the warning names TLC_CLK, TLC_SDI and TLC_SDO at each driver. The fix is a capacitor of 1 µF or
less (100 nF, 0603) from V_LED to GND next to each driver.

**Tests.** Synthetic Gerber files with a slot, a stitched slot and a supply pour with and without its capacitor.
Live runs on pytree's and the bell's released runs.

## EMC.6 HINT.crystal

**Rule.** A note where the graph has a part of kind `crystal` on a board:

- the crystal and its load capacitors next to the MCU's pins, handed to the layout as `layout.near`;
- the tracks as short as possible, and the recommended crystal and circuit where the MCU's maker names them
  (Raspberry Pi, Hardware design with RP2350, 4 and 4.1);
- on the routed board, as information:
  - every part within 25.4 mm of the crystal that is neither its MCU nor one of its load capacitors (SZZA009 2.4.1:
    "No unrelated components should be closer than 1 inch to the crystal");
  - every fast track that passes under it (SPRAAR7J 2: no high-speed traces "under or near crystals").

The load capacitance itself is maker-coverage CK-13.

**Tests.** A graph with a crystal (`kinds.toml` has the kind), synthetic placements. Live run: Raspberry Pi's RP2350A
Minimal design.

## EMC.7 Domain usb: the routed pair

What applies when D+ and D− are routed on the board itself:

- **Series resistors:** 27 Ω in series, next to the chip, for the RP2350 (Raspberry Pi, Hardware design with RP2350,
  5.1).
- **Impedance:** 90 Ω differential, the USB specification. On a 1 mm board, 0.8 mm tracks with a 0.15 mm gap give it.
  On a thicker board it "could be a physical impossibility"; full speed "can be quite forgiving … probably not going to
  be compliant" (same source). JLCPCB's default is 1.6 mm, so a board with USB data on it means a 1.0 mm board, a known
  compromise, or a module.
- **Ground:** solid and uninterrupted under the whole length of the pair (same source). SPRAAR7J lists the USB 2.0 pair
  as a critical signal (1.2).

**Rule**, in the domain usb, when the pins with the roles `dp_*` and `dn_*` are routed on the board:

- both tracks on one layer;
- the pair over ground for its whole length, checked by EMC.5 with the pair as fast nets;
- a note with the board's thickness from the order: at more than 1 mm the 90 Ω are out of reach on two layers, so the
  note names a 1.0 mm board, the compromise, or a module;
- for an MCU whose entry asks for series resistors (the RP2350: 27 Ω), the resistors next to the chip.

All projects plug USB into a module today.

**Tests.** Synthetic files, and Raspberry Pi's RP2350A Minimal design as a live run (1 mm, its pair over ground).

## EMC.8 A plan for the test firmware

Added on the owner's word the same day: "ja", to "Soll ich das als EMC.8 ins Konzept schreiben?".

**Why.** An EMC measurement needs a firmware that keeps the board busy and shows when it fails. That holds for a
pre-check with a near-field probe and for a day in a lab, where every hour spent programming is the dearest one.
edakit does not write that firmware: the contract has no firmware format, and what the firmware must do stays with the
project (handbook 3.5; `docs/concepts/done/requirements.md`, decision 3). But edakit knows from the circuit most of
what it must do.

**What.** `edakit firmware emc` writes it as a plan, `hardware/firmware_emc.json`, and prints it in readable form. The
project's assistant writes the test firmware from it, in the project's language. The plan has four parts.

1. **Emissions, in two stages.**
   - *Typical:* the busiest mode the product has in use. edakit does not know the modes, so the plan names this as a
     gap for the project to fill.
   - *Stress:* everything at once, all the time, to find the sources:
     - the fast nets of EMC.1 running without pause at their clock: a chain shifting continuously, its latch after
       every frame;
     - every output of `channels` on;
     - every PWM net at its `pwm_hz`;
     - a buzzer at its resonance;
     - the highest supply current of the simulation's scenarios, as the check that the stage is complete.
2. **Immunity made visible.**
   - A chain with `read_back` shifts a pattern and compares what comes back, continuously. A mismatch shows on an output
     the plan names: an LED channel, or an MCU pin with an LED.
   - Every input of `inputs` is mirrored: a DIP switch's bits on LED channels, a button press counted and shown. A
     wrong read or a phantom press under a field or a discharge shows at once.
   - A heartbeat on one LED, so that a restart is seen.
   - Together they show whether the board keeps running, recovers by itself or needs a restart. These are the
     performance criteria A, B and C of the immunity standards; the standards were not read for this concept.
3. **The limits the circuit sets**, which the test firmware keeps:
   - **The way in:** a fixed combination of the inputs at power-up, never reached in normal use; for pytree, SW2 and
     SW3 held while plugging in.
   - **Loads that must not stay on:** a buzzer's coil, a motor, a relay or a solenoid behind a transistor runs as in
     use, never steady on, unless the simulation's steady state holds every limit.
4. **The gaps, named:** a fast net without `clock_hz` ("the firmware's clock"), a buzzer without its resonance, the
   product's modes.

**Data.** All of it exists but one value:

- the contract: `pins`, `pwm`, `inputs`, `buses`, `bus_speed`, `chains`, `channels`;
- EMC.1's fast nets;
- the simulation's scenarios.

New is a value `f_res_hz` for the kind `buzzer` in `kinds.toml`, from the datasheet. Today the kind has only
`coil_ohm`.

**A command of its own**, not a section of `firmware.json`: a project whose pre-commit hook runs `edakit firmware
--check` would otherwise have to write its contract again after the update. So the plan is opt-in, and the version is
`patch`.

**pytree.** From today's contract the plan would say:

| Part | What it says for pytree |
| --- | --- |
| Stress stage | TLC_CLK and TLC_SDI shift continuously, at the firmware's clock (no `clock_hz` in the graph). TLC_LE latches after every 24 bits, TLC_OE stays at its active level from `pins`. All 24 channels are on, the star's three outputs on. The buzzer runs at its resonance; the entry has none, and the datasheet gives 2.048 kHz per pytree's `docs/schaltungsbeschreibung.md`. |
| Immunity | the read-back over TLC_SDO, a mismatch shown on the star's red; the eight DIP bits on eight channels; SW2 and SW3 counted |
| Way in | SW2 and SW3 held while plugging in |
| Limit | the buzzer never steady HIGH (the coil and R41 behind Q1) |
| Gaps | the clock, the buzzer's resonance, the modes |

## What stays out

- **Simulation of emissions** (field solvers, near-field models): not text-sized and not checkable by an LLM.
- **A measurement or pre-compliance test:** the owner's, in a lab or with a near-field probe. A project records the
  result in its decision log.
- **Grading by purpose** (handbook 15.4): it grades the regulatory codes. GEO.length and GEO.return are technical checks,
  so each is the same warning for every purpose.
- **What the rows prove:** the regulatory review (M-6) can name the warnings, and the accepted ones with their reasons,
  as layout measures taken. That is no evidence that a board complies; only a measurement is.

## Decisions

Decisions 1 to 3 were taken by the owner on 2026-11-10 in a decision round in Claude Code's form. Decision 4 lists what
Claude decided itself; the owner confirmed it in the same round ("Alles bestätigt"). Decision 5 followed the same
day, on the owner's word.

| # | Question | Recommendation | Alternatives | Decision |
| --- | --- | --- | --- | --- |
| 1 | Scope | all seven steps, in three branches: EMC.1–EMC.4, EMC.5, EMC.6 with EMC.7 – about one and a half working days of session time | EMC.1–EMC.5, about a day, crystal and USB pair left in the concept; EMC.1–EMC.4 alone, about half a day, the return-path rules as review questions only | accepted: all seven |
| 2 | A clock without `clock_hz` (EMC.1, step 2) | it counts as fast; `edakit check --coverage` names every clock counted so | it counts only with `clock_hz` set – every project today would stay unchecked until its graph sets the field | accepted: it counts as fast |
| 3 | Severity of GEO.length and GEO.return | a warning for every purpose, accepted with its reason | graded by purpose like the regulatory codes (handbook 15.4): a note for a board for oneself or a gift, a warning for one sold | accepted: a warning for every purpose |
| 4 | Decided by Claude | (a) a net is fast with edges above 50 kHz (SZZA009 1.3); (b) a series resistor is "next to the driver" within 10 mm, a number no source gives; (c) SPRAAR7J's 5.08 mm hold for capacitors across a gap too; (d) the part fact `t_edge_ns` and the note on long inputs dropped; (e) HINT.supply_entry only on boards with fast nets, 470 pF instead of 100 nF; (f) the live run for crystal and USB pair on Raspberry Pi's RP2350A Minimal design, its licence checked first | – | confirmed |
| 5 | A plan for the test firmware (EMC.8) | `edakit firmware emc`, a command of its own after EMC.1, in a fourth branch | – | added on the owner's word ("ja"), a step like the others |

## The review of 2026-11-10

| # | Finding on the first version | What changed |
| --- | --- | --- |
| 1 | No rule had a source that was read; it said so itself. | SZZA009 read in full, SCAA082A, SPRAAR7J, the RP2350 datasheet and Raspberry Pi's design guide read where cited. The ESP32 and ATmega328P datasheets were searched for output edge times. |
| 2 | Fast nets: every MCU output, PWM net and chain line. That is too broad; SZZA009 1.3 excludes everything below 50 kHz, and on the bell every LED and servo line would have warned. | EMC.1: edges above 50 kHz only. |
| 3 | Fast nets by `clock_hz` and `fn` only. No project sets them, so the check would have run silent. | EMC.1: clocks found by roles count too, and a coverage line names them. |
| 4 | Critical length from an edge time ("a sixth of the edge", 6–7 ps/mm): neither rule was read in a source, and 6–7 ps/mm was wrong for an outer layer. SCAA082A, Table 2 gives 5.8–5.9 ps/mm for microstrip on 1.5 mm FR-4. | Replaced by SZZA009's 4 inches, which needs no edge time. |
| 5 | Part fact `t_edge_ns` from the datasheet: the RP2350, ESP32 and ATmega328P datasheets give no output edge times. | Dropped. |
| 6 | "Reuse GEO.loop's path length": `loop_length_mm` does not pass through pads; pytree's TLC_CLK to U5 came back as none. | EMC.2: pads and vias become nodes of the path. |
| 7 | "`edakit firmware` holds the firmware to the pad setting": the contract (3.5) writes JSON. `--check` compares it with the graph, not with the firmware. | The remedy is the project's firmware; the warning names it, the acceptance records it. |
| 8 | "The RP2350's edges take a few nanoseconds" and "slow slew" as a remedy: the slow slew is the reset value already. | EMC.2: the remedy is the drive, 4 → 2 mA. |
| 9 | 100 nF at the supply entry: SZZA009 asks for below 1000 pF at the connector, for its low ESR at 50–500 MHz. | EMC.4. |
| 10 | Long inputs with internal pull-ups (old point 7): no source gives a length limit. SZZA009 2.4.4 asks for a pull-up on a line to a switch, and the internal one is one. Bell (96–109 mm, 4.7 kΩ) and pytree (36–64 mm) are static inputs. | Dropped; HINT.debounce, HINT.esd and HINT.cable_line stay. |
| 11 | GEO.return's rules with numbers come from SPRAAR7J, written for high-speed interfaces. | EMC.5 says so; the questions of EMC.3 carry the same rules for the layout review. |
| 12 | HINT.crystal and the USB pair: no project has a crystal or USB data on its own board. | Tested on synthetic files and a published design (EMC.6, EMC.7). |
| 13 | The pytree numbers were totals per net, not paths. OE and the star counted as risks, but they are below 50 kHz. | Measured paths; the table above. |
| 14 | "M-6 reads the rows as evidence" claimed too much. | "What stays out": a record of measures taken, no evidence of compliance. |
| 15 | The reviewed version deferred EMC.5–EMC.7 "until the first project that needs it", at "2–3 days" for EMC.5. A check that waits for its project comes too late by construction. The days were a guess at a person's work, not measured against this repository: proposal #103, a check on the same raster, took under four hours from the issue to the merge. | Nothing deferred. Sizes in session time, measured against #103. EMC.5 got simpler: labelling inside a disc instead of a detour path. |

## Sources

Read for this version on 2026-11-10, each downloaded from its maker's site:

- Texas Instruments, **SZZA009**, *PCB Design Guidelines For Reduced EMI* (November 1999), read in full –
  <https://www.ti.com/lit/an/szza009/szza009.pdf>.
- Texas Instruments, **SCAA082A**, *High-Speed Layout Guidelines* (2006, revised August 2017). Read: 1.2 (clock
  signals), 1.3 (transmission lines, Table 2), 1.6 (return current and loop areas) and the split ground planes of 2 –
  <https://www.ti.com/lit/an/scaa082a/scaa082a.pdf>.
- Texas Instruments, **SPRAAR7J**, *High-Speed Interface Layout Guidelines* (2018, revised February 2023). Read: 1.2
  (critical signals), and in 2 plane splits, stitching capacitors, stitching vias and the routing rules –
  <https://www.ti.com/lit/pdf/spraar7>.
- Raspberry Pi, **RP2350 Datasheet**, 9.6 Pads and the pad control registers (`DRIVE` reset 4 mA, `SLEWFAST` reset
  slow). The whole text was searched for output rise and fall times; there are none –
  <https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf>.
- Raspberry Pi, **Hardware design with RP2350**. Read: 4 (crystal oscillator), 5.1 (USB), 5.2 (I/O headers) –
  <https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf>.
- Espressif, **ESP32 Series Datasheet**, and Microchip, **ATmega48A/PA/88A/PA/168A/PA/328/P datasheet**
  (DS40002061B), searched for output rise and fall times of the I/O pins. There are none: the ATmega's rise and fall
  times belong to the external clock and the TWI –
  <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>,
  <https://ww1.microchip.com/downloads/aemDocuments/documents/MCU08/ProductDocuments/DataSheets/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf>.
- ST **AN2867** (oscillator design): not reachable on 2026-11-10 (st.com timed out). Maker-coverage read it for CK-13; it
  is not cited here.
- The projects:
  - pytree: release run `20261101-225744` (`fab/tree/pcb.json`), `hardware/graph/hardware_graph.json`,
    `docs/schaltungsbeschreibung.md`, `docs/hardware.md` D-48, `firmware/leds.py` (`SPI_HZ = 1_000_000`);
  - bell: release run `20261101-142527` (`fab/main/pcb.json`), `hardware/graph.json` and the graphs of
    `variants/{esp32,esp32tht,smd,tht}`;
  - desk-led: `hardware/graph.json`;
  - pedal: `docs/builders/`, and maker-coverage's row on AwesomeStudioPedal.
