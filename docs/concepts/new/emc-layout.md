# EMC in the layout: fast nets, long tracks, return paths, supply entry, crystals, USB data, cables

Status 2026-11-10: open, nothing decided, nothing built. Asked for by the owner: whether edakit's rules cover EMC best
practice, and how likely pytree is to run into trouble because of its longer tracks. A first version listed six gaps
("ja. was ist mit den anderen punkten?"). The owner then asked for a review of it: "review emc-layout .... sind alle
regeln belegt? sind alle regeln im kontext von edakit sinnvoll und umsetzbar?" and "auch anhand von den anderen
projekten überprüfen (glocke, pedal)".

This version is the result of that review, the same day. Every rule now rests on a source that was read; the review's
findings and what they changed are listed at the end. Written against main at `77ee7cb0`.

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

So this version proposes:

| Step | What | Source | Hits in the projects today |
| --- | --- | --- | --- |
| EMC.1 | Fast nets: which nets count, and a coverage line when edakit cannot tell | SZZA009 1.3, 2.6.3 | pytree: the SPI chain |
| EMC.2 | GEO.length: a fast net longer than 101.6 mm from its driver without a series resistor next to the driver | SZZA009 2.4.2, 2.4.3, 2.2.5 | pytree: TLC_CLK 126.5 mm, TLC_SDO 118.4 mm |
| EMC.3 | Questions for the layout review (M-5) in the core domain: ground under fast tracks, gridding, fast tracks at the board edge, Freerouting and fast nets, crystals | SZZA009 2.1–2.6, SCAA082A 1.6, SPRAAR7J 2 | every board with fast nets |
| EMC.4 | HINT.supply_entry: a small capacitor at the supply entry of a board with fast nets, a place for a ferrite | SZZA009 2.2.4, 2.5.4, 2.5.5, 3.3, 4 | pytree: J1 |

Deferred, each with its own trigger:

| Step | What | Waits for |
| --- | --- | --- |
| EMC.5 | GEO.return: the return path of every fast track on the Gerber raster | a second project with fast nets, or the owner's word (2–3 days) |
| EMC.6 | HINT.crystal | the first project with a crystal on its own board |
| EMC.7 | domain usb: the routed USB pair | the first project that routes USB data on its board |

Dropped: the edge time as a part fact (no datasheet gives it), and the note on long inputs with an internal pull-up (no
source asks for a length limit).

All steps read what is text already: the graph, the part entries, the board file, `pcb.json` and the Gerber files.
They leave nothing that exists only in EasyEDA or in someone's head.

## The projects

| Project | Board | Nets above 50 kHz | What the proposed rules would report |
| --- | --- | --- | --- |
| pytree | tree, two layers, RP2350-Zero module; tracks on TOP (pytree's "hinten"), V_LED poured on BOTTOM | the SPI chain to U3–U5: TLC_CLK (1 MHz, `firmware/leds.py`), TLC_SDI, TLC_SDO. LE pulses once per update, and OE, the star and the buzzer switch at 0.5–2 kHz. All of these are below 50 kHz. | EMC.2: TLC_CLK 126.5 mm to U3 and TLC_SDO 118.4 mm from U3, no series resistor (TLC_SDI 92.3 mm passes). EMC.4: J1. EMC.5 if built: no capacitor between V_LED and GND near U3–U5 (only C1 and C4, in the foot). |
| bell (automatic_christmas_bell, all variants: Nano, ESP32, THT, SMD) | main, two layers, Arduino Nano or ESP32 module | none: servo at 50 Hz, LEDs, two buttons with 4.7 kΩ pull-downs | nothing. The first version would have flagged SERVO (66.3 mm) and the button lines (96–109 mm). |
| desk-led | main, battery, switch, LED | none, no MCU | nothing |
| pedal (AwesomeStudioPedal) | no PCB and no edakit project: NodeMCU-32S on wires, five footswitches with 10 kΩ pull-ups and LEDs on 30 cm and more of cable (maker-coverage) | none: footswitches and LEDs are static or slow | Only the cable rules apply. HINT.cable_line and HINT.esd exist; SZZA009 2.5.3 adds the ratio of return wires (EMC.3, cable question). The radio (BLE) is the domain radio's. |

The lengths are measured on the released runs: pytree `20261101-225744`, bell `20261101-142527`. They are the shortest
path over tracks from the MCU's pad to each load's pad, computed by `loop_length_mm` of `edakit/release/fab.py`.

Only one bus on one board is a target today. That sets the size of what is worth building now.

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

## EMC.5 GEO.return – deferred

The check the questions of EMC.3 stand in for, on the Gerber raster.

- **Rule:** for every track of a fast net, the reference copper on the other layer under it. Where it has a gap, the
  return detour: the shortest path in ground copper around the gap, both layers, joined through vias and through
  0 Ω bridges and capacitors between reference nets. Compared with the gap's width.
- **Sources:** as EMC.3.
- **Data:** GEO.copper's raster (`gerber.Copper`) has the copper per net and island, joined through plated holes
  (`net_mask`, the union of islands). New would be a geodesic distance on that raster.
- **Size:** two to three days with negative tests. Today it would find one thing on one board, pytree's V_LED reference
  without a capacitor at the drivers.

*Recommendation:* build it with the second project that has fast nets, or on the owner's word.

## EMC.6 HINT.crystal – deferred

The rules are in EMC.3 (crystal). A hint makes sense where the graph has a part of kind `crystal` on a board. Every
project has its crystal on a module, so it would find nothing today.

*Recommendation:* build it with the first project that has a crystal on its own board, together with `layout.near` for
the crystal and its capacitors as the hand-over to the layout. Raspberry Pi's guide insists on its recommended crystal
and circuit (4, 4.1). The load capacitance is maker-coverage CK-13.

## EMC.7 Domain usb: the routed pair – deferred

What applies when D+ and D− are routed on the board itself:

- **Series resistors:** 27 Ω in series, next to the chip, for the RP2350 (Raspberry Pi, Hardware design with RP2350,
  5.1).
- **Impedance:** 90 Ω differential, the USB specification. On a 1 mm board, 0.8 mm tracks with a 0.15 mm gap give it.
  On a thicker board it "could be a physical impossibility"; full speed "can be quite forgiving … probably not going to
  be compliant" (same source). JLCPCB's default is 1.6 mm, so a board with USB data on it means a 1.0 mm board, a known
  compromise, or a module.
- **Ground:** solid and uninterrupted under the whole length of the pair (same source). SPRAAR7J lists the USB 2.0 pair
  as a critical signal (1.2).

*Recommendation:* build it with the first project that routes USB data. All projects plug USB into a module today.

## What stays out

- **Simulation of emissions** (field solvers, near-field models): not text-sized and not checkable by an LLM.
- **A measurement or pre-compliance test:** the owner's, in a lab or with a near-field probe. A project records the
  result in its decision log.
- **Grading by purpose** (handbook 15.4): it grades the regulatory codes. GEO.length is a technical check, so it is the
  same warning for every purpose.
- **What the rows prove:** the regulatory review (M-6) can name the warnings, and the accepted ones with their reasons,
  as layout measures taken. That is no evidence that a board complies; only a measurement is.

## Open decisions

1. **Scope now.** Recommendation: EMC.1–EMC.4 now; EMC.5 with the second project that has fast nets; EMC.6 and EMC.7
   with their first project. The alternative is EMC.5 now as well, two to three days more.
2. **A clock without `clock_hz`** (EMC.1, step 2). Recommendation: it counts as fast, and the coverage line names it.
   The alternative is that it counts only with `clock_hz` set; then pytree's chain would not count until its graph sets
   the field.
3. **Severity of GEO.length.** Recommendation: a warning for every purpose, accepted with its reason. The alternative is
   grading by purpose like the regulatory codes.

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
| 11 | GEO.return as the first step: two to three days of work for a single finding on a single board today. Its rules with numbers come from SPRAAR7J, written for high-speed interfaces. | Deferred (EMC.5); the questions of EMC.3 carry the rules now. |
| 12 | HINT.crystal and the USB pair now: no project has a crystal or USB data on its own board. | Deferred with their triggers (EMC.6, EMC.7). |
| 13 | The pytree numbers were totals per net, not paths. OE and the star counted as risks, but they are below 50 kHz. | Measured paths; the table above. |
| 14 | "M-6 reads the rows as evidence" claimed too much. | "What stays out": a record of measures taken, no evidence of compliance. |

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
