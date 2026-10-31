# A second walkthrough: a 555 blinker on KiCad

Status 2026-10-31: concept, asked for by the owner; nothing built, nothing run. Written against main at `2f4628a`. The
owner's word the same day: a simulation over time is out of scope for edakit – the walkthrough builds the circuit and
evaluates the board as far as edakit can without one. Three decisions are open, and Claude's own choices wait for the
owner's confirmation (section "Decisions").

## Goal

Switch it on and a red LED blinks about once a second, from two AAA cells; switch it off and the cells deliver
nothing. One board, drawn in KiCad (`toolchain = "kicad"`). The walkthrough takes it from the idea to the released
manufacturing files the way handbook 17 took the coin cell board, and tells only what differs. Chapter 17 stays the
first reading.

What chapter 17 does not show, and this one does:

1. **KiCad end to end on a real project.** No board has gone through the KiCad tool chain to a release (handbook
   16.8). The tested parts so far are the led-bar example with test footprints in CI. Here the footprints come from
   the real LCSC data – through-hole pins, a slide switch's pegs, a SOIC-8 – and the gate `--eda` runs with every
   sign-off up to RELEASED, followed by `edakit export`.
2. **An IC with a supply range.** The NE555 needs 4.5 V, and two AAA cells give 3.2 V fresh and about 2 V used
   (maker-coverage, case 24). The board needs a CMOS 555, and LIM.range holds the part's `vdd_op_min_v` against the
   used cells.
3. **Cells in series, an end voltage and a power switch.** Two cells in one holder, "off means off" as a requirement
   with a number, and a current budget per phase as its evidence (the load's `expect`, LIM.i).
4. **A circuit whose function is a time.** edakit evaluates what the board does at each DC state. How fast it blinks
   is computed in the decision log and measured on the finished board (section "Scope").
5. **The graph as TOML from the start** (`hardware/graph.toml`, handbook 3.1). The coin cell example still has the
   JSON form.

Against the yardstick (`docs/concepts/done/design-as-text.md`): nothing exists only in KiCad. The KiCad project is
generated into `build/` and not versioned (kicad-toolchain, decision 5). The timing computation is text in
`docs/decisions.md`, and the acceptance step that measures it is in `hardware/requirements.toml`, so nothing is left
only in someone's head either.

## Scope: what edakit evaluates, and what it does not

| Evaluated by edakit (stages P, G, E, S, L, F) | Not evaluated: a computation in the decision log, and the acceptance M-4 |
|---|---|
| every part inside its supply range at fresh and used cells (LIM.range: the 555's `vdd_op_min_v`) | the blink frequency and duty cycle |
| the LED's current and power in the phase it is lit, at both Vf corners (LIM.i, LIM.p, SIM.state) | the first period after switch-on (the capacitor starts at 0 V, not at 1/3 VDD) |
| the LED dark in the other phase (SIM.state) | the edges, and the 555's current spikes when its output switches |
| the current from the cells in each phase and with the switch open (LIM.i on the load's `expect`) | the mean current over a period, and with it the battery life |
| a cell upside down (PATH.reverse) | |
| decoupling, pins left open, levels at the 555's inputs (REQ.missing, LVL.undefined) | |
| parts, stock, schematic = graph, layout, copper, DRC, manufacturing files (P, S, L, F) | |

The timing becomes the designer's computation, like R1's in 17.6. With a CMOS 555, whose thresholds sit at 1/3 and
2/3 of VDD, the classic astable gives t_high = ln 2 · (RA + RB) · C and t_low = ln 2 · RB · C, independent of the
supply. As an example: RA = 10 kΩ, RB = 680 kΩ, C = 1 µF give t_high = 0.478 s, t_low = 0.471 s, f ≈ 1.05 Hz, about
50 % duty. The spread of R and C goes in the same note. A capacitor's tolerance and DC-bias loss come from its parts
entry (`tolerance`, `dc_bias`), and the 555's timing error from its datasheet. The requirement's evidence is the
acceptance step: count the flashes for 60 s from a lab supply at the fresh and at the used voltage.

## The circuit: a sketch, not the design

```text
BT1 2×AAA ──► SW1 slide switch ──► [reverse protection?] ──► VDD
                (common – throw_a)                              │
                                                                ├── C1 100 nF to GND (decoupling)
                                                                ├── U1 CMOS 555, astable: RESET to VDD, CONT open or 10 nF
                                                                │     RA VDD–DIS, RB DIS–THR/TRIG, C THR/TRIG–GND
                                                                └── U1 OUT ──► R_LED ──► D1 red ──► GND
```

| Part | Kind | What it must do | Candidates (to be confirmed by `edakit part search` and signed against the datasheet) |
|---|---|---|---|
| BT1 | battery_holder | two AAA cells in series | a 2×AAA holder, through-hole or SMD (decision 1) |
| SW1 | switch | break the cells' plus; SPDT, used as on/off | a slide switch, through-hole or SMD |
| U1 | ic | astable down to the used cells | TLC555 (TI, 2–15 V), LMC555 (TI, 1.5–15 V), ICM7555 (Renesas, 2–18 V); ranges as recalled, to be read from current datasheets at sign-off |
| RA, RB, C | resistor, capacitor | the timing | from the computation above; C X7R or C0G, judged by DC bias and tolerance |
| C1 | capacitor | decoupling at VDD | 100 nF, as the 555's pin `needs` say |
| R_LED, D1 | resistor, led | visible at the used cells | a red LED; whether D1 hangs from OUT (lit while OUT is high) or from VDD into OUT (lit while OUT is low) depends on the 555's output stage at 2 V, so the design decides |

What the checks are likely to find. These are expectations to be confirmed by the run, not results:

- **The LED at the end voltage.** A red LED needs about 1.7–1.8 V at 1 mA. At 2.0 V, minus what the 555's output
  stage drops, it gets little or nothing. This is the counterpart of the green LED in 17.6 (SIM.state). The answers
  are another end voltage in the requirement, less current with an efficient LED, or a 555 whose output drops less.
- **A cell upside down (PATH.reverse).** In 17.6 the LED blocked by itself. Here the 555's VDD sees the reversed
  cells, and a CMOS IC takes about −0.3 V. A Schottky in series costs 0.2–0.3 V of 2 V. A P-MOSFET (block
  `reverse-pmos`) needs a gate threshold well below the used voltage. Whatever the checks show, the decision is made
  in that step.
- **The current in the off phase.** While OUT is low, DIS pulls RA to ground: VDD / RA = 0.32 mA at 3.2 V with
  10 kΩ, more than the 555 itself draws. The load's `expect` shows it, and the remedy is a larger RA, or the CMOS
  variant with one resistor from OUT to the capacitor.
- **The 555's inputs.** THR and TRIG are comparator inputs. Whether they pass LVL as `analog` pins without a false
  finding is a point to check (gap E2).

## The 555 in the simulation, at DC

There is no new behaviour model and no transient run. The 555 is behaviour `logic` (handbook 5.1): `icc_a` at its
supply pin, OUT push-pull with `r_out_ohm` from the datasheet's VOH/VOL at the used voltage, and DIS as an output
with `drive = "open_drain"`. The two phases are two DC states:

| Load | U1 OUT | U1 DIS | `leds_on` | `expect` |
|---|---|---|---|---|
| `lit` | high | off (released) | `["D1"]` (if D1 hangs from OUT) | BT1 `i_max_a` |
| `dark` | low | low | `[]` | BT1 `i_max_a` |
| `off` | – (SW1 at `throw_b`) | – | `[]` | BT1 `i_max_a = 1e-6` |

× cell states `fresh`, `used` (and `reversed` for PATH.reverse) × the LED's Vf corners.

**Gap E1:** a component's `states` hold for every scenario (handbook 3.1). A load cannot switch OUT and DIS today,
so only one phase would be simulated. A load's `gpio` sets an MCU's outputs per net, but nothing does that for a
part with behaviour `logic`. E1 adds `states` to a load in sim.json, taking precedence over the component's:
`"dark": {"states": {"U1": {"OUT": "low", "DIS": "low"}}, "leds_on": []}`. It is a DC operating point
like any other and does not bring timing in. It also serves any logic part whose output differs between loads (an
alert asserted in one load only). It would be built test first with the skill add-feature, before step 4. Without it
(decision 3), only the lit phase is simulated, and the dark phase is computed in the notes.

## What is expected to break, and how it is handled

As in 17.13, every fault the run finds is fixed in edakit on its way, with add-feature or add-rule, and listed in the
chapter's last section. Known beforehand:

| # | Where | What | When |
|---|---|---|---|
| E1 | simulation | `states` per load (above) | before step 4, if decision 3 is (a) |
| E2 | LVL | the 555's THR/TRIG as comparator inputs: no false LVL finding on the timing capacitor's net | in step 5, if it shows |
| E3 | KiCad | the first real LCSC footprints through `pcb apply`: through-hole pads, slots or oval holes, polygon pads, the library's silkscreen (16.8, "open") | step 11 |
| E4 | KiCad | a hand-soldered through-hole part on the bottom, if decision 2 is (a): mirroring, GEO.spacing's hand-solder keep on the top-side joints, the polarity sheet | step 11 |
| E5 | gate | `gate --eda` with every sign-off up to RELEASED, and `export` with `kicad_main.zip` (16.8, "open") | step 12 |

## The steps

The same fourteen steps as 17.1. The column "New" says what this chapter shows instead of repeating chapter 17.

| | Step | Who | New compared to chapter 17 |
|---|---|---|---|
| 1 | Set up | `/edakit:new-project blinker-555 main` | the tool chain answered with KiCad 10: `toolchain = "kicad"`, no EasyEDA document names, `graph = "hardware/graph.toml"`; `edakit doctor` shows KiCad instead of the bridge |
| 2 | What it must do | `/edakit:requirements` | an end voltage per cell; "off means off" with a number; a requirement on a time (the blink rate) whose only evidence is `accept` |
| 3 | Parts | part-search, part-selector | an IC signed against its datasheet: supply range, output stage at 2 V, DIS, pin `needs`, `float_ok` on CONT |
| 4 | Circuit | `/edakit:circuit-design` | the graph written as TOML, `edakit graph json --write`; three loads instead of two (E1) |
| 5 | What the checks found | Claude proposes, you decide | the findings above; the timing computation as a decision, not as a check |
| 6 | Stock and cost | `edakit stock`, `cost`, `order` | through-hole parts by hand (`bom = false`) beside an Economic order, or a PCB only (decision 1) |
| 7 | Drawing and hand-over | `schematic draw`, `handover` | the switch at the edge, the LED where it is seen, the holder's side |
| 8 | Reviews | electrical-reviewer, regulatory-reviewer | M-1 on an IC; M-6 for a battery board for private use. Its result is support, not legal advice: it claims no correctness, and nothing in it is legally guaranteed |
| 9 | The gate without a tool chain | `edakit gate` | – |
| 10 | EDA project | – | nothing to do: edakit writes `build/edakit/kicad/main/` |
| 11 | Layout | `/edakit:pcb-round` in a session of its own | `pcb place --rest` (KiCad has no auto-layout), `pcb apply`, `route all` with kicad-cli's zone fill and DRC, `silk apply`; the files opened in KiCad to look at only |
| 12 | Release | `edakit gate --eda`, `edakit export` | stages S, L, F on kicad-cli's netlist, ERC, DRC, Gerber, drill and position file |
| 13 | Order | `edakit cart`, `/edakit:cart` | decided at the release (Claude's choice 6) |
| 14 | Acceptance | you | the blink rate counted at two voltages, the off current measured: the evidence the simulation does not give |

Where it runs: steps 3 to 12 need ngspice, Freerouting and KiCad 10's `kicad-cli` (handbook 2.2, 16.2). None of them
is installed in the cloud container this concept was written in, so the run takes place on the owner's machine or in
a container with KiCad's image, as in the CI job `kicad`.

## Deliverables

- `examples/blinker-555/`: `edakit.toml` with `toolchain = "kicad"`, `hardware/graph.toml` and the generated
  `graph.json`, `requirements.toml`, `parts/`, `sim.json`, `schematic.toml`, `boards/main.toml` with
  `main.geometry.json`, `stock.json`, `signoff.json`, `docs/decisions.md`, the pictures of `schematic draw`,
  `pcb plan` and `silk apply`, and a README as for coin-cell-led.
- `handbook/18-walkthrough-kicad.md`, "Walkthrough 2: a 555 blinker on KiCad", with real outputs, shortened where a
  `…` stands. Also its row in `handbook/README.md`, a reading path for KiCad (1 → 2 → 16 → 18), and the example's row
  in the README.
- `tests/test_walkthrough_kicad.py`: what the chapter quotes still holds (check, sim), as `tests/test_walkthrough.py`
  does for chapter 17.
- E1 to E5 as needed, each with its test, and the handbook chapters they touch (3, 5, 16).
- `TODO.md`: the KiCad live test's steps 1, 3, 4 and 5 count as done on a real project once the example is released.
  Steps 2 (the led-bar copy), 6 (the placer on both tool chains) and 7 (the bell) stay open.

## Decisions

Open, each with the recommendation first:

| # | Question | Options |
|---|---|---|
| 1 | Who assembles | **(a)** JLCPCB Economic for the SMD parts (555 in SOIC-8, 0805), holder and switch through-hole by hand: the KiCad chain's BOM and position file go to an assembler for the first time, and through-hole pads come in with them · (b) everything through-hole and hand-soldered, a PCB only (`[release] assembly.sides = []`): the classic kit, with no BOM or position file · (c) everything SMD and assembled, holder and switch included, where JLCPCB stocks them for Economic |
| 2 | Where the holder sits | **(a)** on the bottom, the board about the holder's size, everything else on top: compact, and a bottom-side part through KiCad (E4) · (b) on top beside the electronics, a larger board on one side |
| 3 | The dark phase in the simulation | **(a)** build E1, `states` per load, before step 4: both phases checked at every corner · (b) only the lit phase simulated, the dark phase computed in the notes |

Taken:

| # | Decision | By |
|---|---|---|
| T | A simulation over time is out of scope: blink rate, duty cycle, start-up and edges are computed in the decision log and measured in the acceptance (M-4) | the owner, 2026-10-31 |
| 1 | Handbook chapter 18, example `examples/blinker-555`, test `tests/test_walkthrough_kicad.py` | Claude, to be confirmed |
| 2 | The graph as TOML from the start | Claude, to be confirmed |
| 3 | Alkaline AAA cells; the end voltage per cell (expected 1.0 V, 2.0 V for the pair) is fixed with the owner in step 2 | Claude, to be confirmed |
| 4 | A CMOS 555, chosen by its supply range. The chapter shows what LIM.range says about an NE555 only if the first choice is one; no mistake is staged | Claude, to be confirmed |
| 5 | The run takes place where KiCad 10, ngspice and Freerouting are installed | Claude, to be confirmed |
| 6 | Whether real boards are ordered (and M-4 run on them) is decided at the release, as in chapter 17 | Claude, to be confirmed |
| 7 | The KiCad live test's steps 2, 6 and 7 stay in `TODO.md`; this walkthrough covers 1, 3, 4 and 5 on a real project | Claude, to be confirmed |

## Sources

- edakit at `2f4628a`: handbook [16](../../../handbook/16-kicad.md) (16.8: what KiCad 10 confirmed and what is
  open), [17](../../../handbook/17-walkthrough.md), [5](../../../handbook/05-simulation.md) (5.1 behaviour `logic`,
  loads and their `expect`, the switch's `throw`), [3](../../../handbook/03-hardware-graph.md) (3.1 `states`, the
  graph as TOML); [kicad-toolchain.md](../done/kicad-toolchain.md) ("Live test", decision 5);
  [maker-coverage.md](../done/maker-coverage.md) (case 24: NE555 at 3.3 V); [walkthrough-gaps.md](../done/walkthrough-gaps.md);
  `edakit/catalog/kinds.toml` (`switch`, `battery_holder`, `ic`, the capacitor's `tolerance` and `dc_bias`);
  `edakit/cost.py` (`sides = []`: the PCB only); `TODO.md` (the KiCad live test).
- 555 timing: the astable's t_high = ln 2 · (RA + RB) · C and t_low = ln 2 · RB · C, as in TI's NE555 and TLC555
  datasheets (application section, astable operation).
- The supply ranges of NE555, TLC555, LMC555 and ICM7555 are as recalled when this was written. They are read from
  the current datasheets when the part is signed off in step 3.
