# EMC in the layout: return paths, edges, the reference planes, USB data, crystals, cables

Status 2026-11-10: open, nothing decided, nothing built. Asked for by the owner. The question was whether edakit's rules
cover EMC best practice and how likely pytree is to run into trouble because of its longer tracks. The answer named
the return paths as the gap, and the owner said "ja. was ist mit den anderen punkten?". This concept covers every gap
that answer listed. Written against main at `0c8007db`.

The pytree numbers are measured on the released run `20261101-225744` (`hardware/release/reports/…/fab/tree/pcb.json`,
the total track length per net) and taken from its graph and `docs/schaltungsbeschreibung.md`. The rules of thumb
below are textbook values. No source was opened for this concept; they are read when a step is built (Sources).

This concept supports layout and covers technical risk only. It is not legal advice, guarantees nothing legally and
makes no claim to be correct. Whether a board meets EMVG § 6 or 2014/30/EU stays with the regulatory review (M-6,
handbook 15).

## The short answer

edakit checks EMC where a project once got it wrong:
- GEO.loop: the switching loop of a regulator, if it is listed;
- HINT.switcher, HINT.esd, HINT.cable_line, HINT.inductive;
- the decoupling capacitor next to each IC (SYNC.plan);
- the nets kept apart (`layout.apart`, GEO.spacing).

GEO.pour fills copper for looks and for missing fills, not for EMC.

Six things are missing. Two of them carry most of the risk on the boards edakit makes, two-layer boards with a bought
MCU module:

1. **Return paths.** Does every fast signal have reference copper under it all the way, and where the reference changes
   net, a capacitor or a via that carries its return current across?
2. **Edges and lengths.** Is a line that switches in nanoseconds longer than its edge allows, without a series
   resistor or a slower pad?

The other four are smaller or wait for a project that needs them:

3. Capacitors between the planes, part of 1.
4. USB data on the board.
5. Crystals on the board.
6. The supply cable as an antenna.

A seventh point is pytree's own: high-impedance inputs on long tracks. It comes with 2.

All six read what is already text: the graph, the part entries, the board file, `pcb.json` and the Gerber files. They
leave nothing that exists only in EasyEDA or in someone's head. One new part fact, the edge time of an output (2),
comes from the datasheet into the part entry.

## What pytree shows

| Point | pytree | Effect |
|---|---|---|
| 1 Return paths | CLK, SDI, LE and OE run on the back from the module to U3–U5. The front is the V_LED plane. The only capacitors between V_LED and GND are C1 and C4, in the foot (22 µF each). Next to the drivers there is none, only 100 nF on 3V3 (C5, C7, C9). GND in the foot (GND_B1) reaches GND in the tree through the single 0 Ω bridge R55. | The return current of each edge takes a detour through the foot. This is the classic source of radiated emissions. |
| 2 Edges and lengths | Total track length: TLC_OE 138 mm, TLC_LE 135 mm, TLC_CLK 127 mm, TLC_SDO 119 mm, TLC_SDI 92 mm. The clock is 1 MHz (`SPI_HZ`), but the RP2350's edges take a few nanoseconds. No series resistor. | Above roughly 50 mm (rise time 2 ns, rule of thumb below), a clock line can ring and clock a shift register twice. pytree would notice through its read-back at start (D-22). |
| 3 Planes | as in 1 | as in 1 |
| 4 USB data | none on the board (J1 carries VBUS and GND only; data only at the module's own receptacle) | – |
| 5 Crystal | on the module only | – |
| 6 Cable | USB power cable to the hill, then W1 to J1. OE switches up to 24 × 9.6 mA at 1 kHz. Only C1 sits at the entry; there is no ferrite and no 100 nF at J1. | Conducted noise on the cable. Small at 1 kHz. |
| 7 Inputs | DIP_D0…D7 36–64 mm long, BTN_CONFIRM 55 mm, all with the internal pull-up | Read only on confirm and static, so a wrong read means pressing again. |

BUZZER_P and BUZZER_N are the longest nets (255 and 304 mm), but they carry 85 mA at 0.5–2 kHz with a slow BJT edge
and run as a pair in one channel. Below the EMC test bands this is no risk worth a check. The star's cathode lines
(170–190 mm, 8 mA PWM at 1 kHz through Q2–Q4) are the same.

## 1 Return paths and the reference (GEO.return, new)

**Rule.** Take each net that carries fast edges:
- a clock (`clock_hz`, `fn: "spi.sck"`);
- a PWM net (`pwm_hz`);
- a chain's common lines (`chains.common`);
- an MCU output (`pins.dir = out`);
- every net whose driver has an edge time (2).

Along each of its tracks, the copper that carries its return is a ground net, or a supply net decoupled to that ground.
On a two-layer board that copper is the other layer under the track, and the same layer's pour within a small distance
of the track. The rule reports:

- **a gap**: track length without reference copper, a slot or the edge of a pour, above `max_gap_mm`;
- **a change of the reference net** (GND_B1 → GND, V_LED → GND) with nothing within `transfer_mm` that carries the
  return across. That can be a via of the same net, a capacitor between the two nets, or a 0 Ω bridge between them
  that the graph knows (3.3);
- **an end without its ground**: at the driving and the receiving pin, the reference is not the part's ground and no
  capacitor between the reference and that ground lies within `transfer_mm`. This is point 3.

**Data.** The tracks with net and layer come from `pcb.json`. The copper per net and island is GEO.copper's raster
(`gerber.Copper`). The grounds come from the graph (PATH.ground, `grounds`); the capacitors are the parts of kind
capacitor between two nets. Everything is there already; the check is a new pass over the raster.

**Severity.** A warning, like the other new GEO checks while they are new. A board accepts each row with its reason.

**pytree.** The rule would warn at U3–U5: the reference is V_LED, with no V_LED–GND capacitor within reach. It would
also warn wherever a line from the foot changes from GND_B1 to GND away from R55. The fix would have been one 100 nF
from V_LED to GND at each driver: three 0603 parts on the back, a few cents.

## 2 Edges and lengths (GEO.edge, new; a part fact `t_edge_ns`)

**Rule.** A track counts as electrically long when its one-way delay is more than about a sixth of the driver's edge
time. On FR-4, an outer layer gives about 6–7 ps/mm, so a 2 ns edge allows about 50 mm and a 5 ns edge about 120 mm.
For each net driven by an output with a known edge time:

- **a warning** when its longest path from the driver to a load is above that length, and no series resistor sits at
  the driver (one resistor of 10–100 Ω between the pin and the track, within a few millimetres);
- **a note** with the length and the critical length otherwise, so a project sees its margin.

**Data.**
- The new part fact `t_edge_ns`, the rise or fall time of an output pin from the datasheet. A module's entry (the
  RP2350-Zero) takes the value of its MCU at the pad's default drive. Unknown is left out, not guessed: `edakit check
  --coverage` names the nets without it.
- The path length comes from `pcb.json`, along the tracks from the driver's pad to each load's pad, as GEO.loop
  measures already.
- The firmware contract (handbook 3.5) can carry a slower pad, a lower drive or slew setting. The check then uses the
  slower edge, and `edakit firmware` holds the firmware to it.

**Inputs (point 7).** The same pass names each input with only an internal pull-up (`pull.by = internal`) whose track
is above `input_mm`. It is a note: an external pull-up or an RC. HINT.debounce already says this for buttons; the note
adds the length.

**pytree.** With an RP2350 edge of about 2–3 ns, CLK, LE, OE and SDI would warn (92–138 mm, no series resistor). The
remedy without new hardware: a lower SPI clock (100–250 kHz; 24 bits still take less than 0.3 ms), the lowest pad drive
and the slow slew, written into the firmware contract.

## 3 Capacitors between the planes

Part of 1, "an end without its ground". The decoupling of SYNC.plan stays as it is: a capacitor from each IC's supply
to its ground. What is new is a capacitor from a plane used as a reference (a poured supply) to the ground of the parts
whose signals run over it. Without a check of its own, it needs no code of its own.

## 4 USB data on the board (domain usb)

What is missing only matters when D+ and D− are routed on the board itself. That is a bare MCU, or a receptacle that
leads to a module's pins. None of the projects at hand does this. Every one plugs USB into a module.

Proposed, for the domain usb when its roles `dp_*` and `dn_*` are routed:
- D+ and D− on one layer;
- a length difference within a limit;
- the pair over unbroken ground (GEO.return with the pair as one net);
- no via in the pair.

Full speed (12 Mbit/s, RP2040 and RP2350) is not critical at a few centimetres. High speed (480 Mbit/s) needs 90 Ω
differential, which needs the maker's stackup: JLCPCB's 1.6 mm two-layer board makes 90 Ω hard. That waits for a
project that needs it.

**Recommendation.** Build it with the first project that routes USB data, not before.

## 5 Crystals on the board (HINT.crystal, new)

Common advice:
- the crystal and its load capacitors next to the MCU's pins;
- short tracks;
- ground under them and around them;
- no other signal under the crystal or between it and the MCU.

The load capacitance itself is maker-coverage CK-13. Crystals are kind `crystal` in `kinds.toml`, and no project has one
on its board.

**Recommendation.** A hint (note) when the graph has a crystal on a board, with `layout.near` for the crystal and its
capacitors as the hand-over to the layout. A GEO check only once a project needs it.

## 6 The supply cable (HINT.supply_entry, new; or HINT.cable_line extended)

A cable that leaves the enclosure is the board's antenna below about 300 MHz, the supply cable included. Today
HINT.cable_line is about signal lines, and HINT.esd is about connectors that people touch.

**Rule.** The hint applies where supply and ground enter the board from a connector that leaves the enclosure. It
suggests:
- a ceramic capacitor (100 nF) next to the connector, beside the bulk capacitor;
- for a board with fast edges, a place for a ferrite bead or a 0 Ω in the supply line, so that a measured problem
  becomes a part change, not a new board.

**Data.** The matcher `power_input` of `engines/hint.py` exists already.

## What stays out

- **Simulation of emissions** (field solvers, near-field models): not text-sized and not checkable by an LLM. edakit
  does not do it.
- **A measurement or a pre-compliance test:** that is the owner's, in a lab or with a near-field probe. A project can
  record its result in the decision log.
- **Grading by purpose** (handbook 15.4): it grades the regulatory codes. GEO.return and GEO.edge are technical, so the
  same warning for every purpose is proposed. The regulatory review (M-6) reads their rows as evidence for EMC "in
  substance" of a board given away (EMVG § 6), and for the technical file of a board that is sold.

## Steps

| Step | What | Size |
|---|---|---|
| EMC.1 | GEO.return on the raster: gap, reference change, end without its ground (points 1 and 3) | about a day, with negative tests from the pytree run |
| EMC.2 | part fact `t_edge_ns`, the path length per net, GEO.edge with the firmware contract's pad setting, the note for long inputs (points 2 and 7) | about a day |
| EMC.3 | HINT.supply_entry, or HINT.cable_line extended (point 6) | an hour |
| EMC.4 | HINT.crystal (point 5) | an hour |
| EMC.5 | domain usb: the routed pair (point 4) | with the first project that routes USB data |
| EMC.6 | handbook 7 (layout) and 8 (gate), and the regulatory review reading the new rows | with each step |

Each step is a branch with its fragment, `patch`: a new check, nothing a project must do.

## Open decisions

1. **Scope:** all of EMC.1–EMC.4 now, with EMC.5 waiting for a project. Or only EMC.1 and EMC.2.
   *Recommendation: EMC.1–EMC.4; the hints are small.*
2. **Severity of GEO.return and GEO.edge:** a warning for every purpose, or graded by purpose like the regulatory codes.
   *Recommendation: a warning, not graded.*
3. **Edge time unknown:** GEO.edge checks only drivers with `t_edge_ns`, or uses a conservative default (1 ns) for an
   MCU output without it. *Recommendation: only with the fact, plus the coverage line. edakit leaves unknown values
   out.*
4. **pytree:** nothing to do for the five gifts, or the firmware remedy of 2 (lower SPI clock, pad drive) in pytree's
   own repository. That decision is pytree's.

## Sources

To be read when the steps are built; none was opened for this concept:

- the rule of thumb for the critical length (one-way delay above about a sixth of the edge time) and 6–7 ps/mm on
  FR-4: textbook values, to be backed by a source that is read, for example TI's high-speed layout guidelines
  (SPRAAR7) or Ott, *Electromagnetic Compatibility Engineering* (2009);
- return paths, the change of the reference plane and stitching capacitors: the same sources;
- the RP2350's pad edge times and drive settings: the RP2350 datasheet, section on the GPIO pads;
- crystal layout: ST AN2867 (already read for maker-coverage CK-13) and Raspberry Pi's hardware design guide for the
  RP2350;
- USB 2.0 full and high speed on the board: the USB 2.0 specification, chapter 7, and the maker's impedance
  calculator;
- pytree: release run `20261101-225744` (track lengths from `fab/tree/pcb.json`), `docs/schaltungsbeschreibung.md`
  (Power Supply, LED Driver, layout notes), `docs/hardware.md` D-48, `firmware/leds.py` (`SPI_HZ = 1_000_000`).
