# To be checked, clarified, fixed – what the walkthrough left open

Status 2026-10-31: settled. Collected, decided and built the same day – A1 to A5 fixed, B1, B3, B4, B5, B7 and B8
checked and built, C1 to C4 decided by the owner (section "Decisions"), C1, C2 and C4 built. Left are runs live in
EasyEDA and at JLCPCB, kept in `TODO.md` (section "State after the build").

The walkthrough of handbook 17 took `examples/coin-cell-led`
from the setup to a released round board, on edakit main after rules at scale. What it found and closed on the way is
in handbook 17.13. Left open are the points below: from the reviews M-1 (electrical-reviewer), M-5 (pcb-reviewer) and
M-6 (regulatory-reviewer), from the outputs of the runs, and from what the bell session reported on the side. Each
says where it was seen.

- **A** – edakit does or says something wrong: to be fixed.
- **B** – a check that does not cover what it seems to cover, or an assumption nobody has tested live: to be checked
  first.
- **C** – a decision of the owner.

## A. To be fixed

| # | Gap | Seen in | Effect today | Proposal |
|---|---|---|---|---|
| A1 | **LED power not held.** The simulation computes `p` for resistors, transistors and MOSFETs only (`engines/sim.py`); an LED gets its forward current (LIM.i) and its reverse voltage (LIM.v), not its power | walkthrough sim: `LIM.p` rows for R1 only, although D1's entry has `p_max_w = 0.065` | an LED run below its `if_max_a` but above its `p_max_w` (a high Vf, a hot ambient) passes | `vf × if` against `p_max_w` where the entry has it, as LIM.p |
| A2 | **Fix text of STRUCT.entry for a pin mismatch.** It says "Create the entry (part-search skill); edakit part import reads pins from the library symbol" | 17.6, D1 with the red LED's entry and the green LED's pins | the advice fits a missing entry, not pins that differ from it | a fix per case: missing entry vs. pins that differ (swap names and nets, or correct the entry) |
| A3 | **Offline gate names a signed M-5 as open.** Without stage F the fab hash is unknown, so `edakit gate` lists "M-5 open" even when M-5 is signed for the current files | example README, offline `edakit gate` after the release | reads as if the review were missing | "M-5: signed for fab f958…, checked by stage F" – the hash bound, not open |
| A4 | **A degenerate edge strip.** Freerouting skipped "keepout zone 'R5_TOP' … geometry is degenerate" | `route all` on the round board (48 chords, 66 edge strips) | one strip of the outside of the board missing in the DSN; routing kept the edge clearance this time | drop strips of (near) zero area in the DSN writer; a test with the circle outline |
| A5 | **Polarity sheet cut off.** BT1's picture ends before the silkscreen "+" at (40.3, 24) | M-5, `fab/polarity_main.png` | M-2 compares the preview with a picture that misses the mark it is about | the sheet's crop includes the part's GEO.mark texts |

## B. To be checked

| # | Question | Seen in | Why it matters | How to check |
|---|---|---|---|---|
| B1 | **GEO.ring for vias** reports "narrowest ring 1.000 mm"; the vias are 0.61 mm on a 0.305 mm hole, a ring of 0.15 mm. Is it measuring the GND pour around the via? | M-5, protocol L, row GEO.ring | a via with too thin a ring would pass under a pour | a via without pour in a test, and one with |
| B2 | **The hole unit of `footprint build`.** `pad_args` writes holes in mil, "an assumption the live run of step 3.6 has to confirm"; `getAllPinsByPrimitiveId` gives them in 10 mil (fixed in 8bdb933) | the hole fix of 2026-10-31 | if `PCB_PrimitivePad.create` takes 10 mil too, own footprints get holes ten times too large | build a footprint with a 1.0 mm hole live, read it back three ways (state `Hole`, `getAllPinsByPrimitiveId`, Gerber drill) |
| B3 | **GEO.silk under a body.** A designator inside the footprint box passes, also where the part's body is larger than its footprint – BT1's designator lay under the cell | M-5, note 1 (fixed in the example by `[silk] place`) | a designator nobody can read once the part is in | GEO.silk counts a body larger than the footprint (the cell from the parts entry) as covering |
| B4 | **Economic board with `[tooling]` but no `[order]`.** FILES.order runs only with `[order]` or `[cart]`; without them no `order.md` says the tooling holes are the customer's | M-5, note 3 (fixed in the example by `[order] remark`) | the form left at "Added by JLCPCB": the maker drills its own holes on the face people see | a warning of FILES.order: `[tooling]` on an Economic board, nothing that tells the maker |
| B5 | **Hand-soldered SMD tabs.** `hand_solder_keep_mm` (GEO.spacing) covers through-hole pads of `bom: false` parts only; BT1's SMD tabs are soldered by hand too | M-5, note 4 (withdrawn: the key checks nothing there) | a via or a foreign pad next to a hand-soldered SMD tab is not looked at | whether such tabs need the same keep, on the side the part sits on |
| B6 | **What JLCPCB's form shows today.** The profile says the order number is gone since May 2026 – nobody has read it off the form; and whether Economic PCBA takes a round board on two customer tooling holes without rails | M-5 "could not check", FILES.order "not yet read off the form" | a mark on the visible face, or an order on hold | at the next order: step 0 of ordering.md on a round board |
| B7 | **The bell's two reports of 2026-10-30.** A silkscreen check (L-17 then) failed on boards printed by an older `silk apply` (no `silk_footprints_<b>/`); `gate --easyeda` leaves other schematic tabs open, and the BOM tool mixed tabs | the bell session | a false finding after an update; a BOM from the wrong schematic | whether either still holds after rules at scale (`edakit explain L-17`) |
| B8 | **KiCad live tests on KiCad 9.** `tests/test_kicad_live.py` runs whenever `kicad-cli` is on PATH and fails two tests with 9.0.8 | every full run on this machine | a red local run that is no regression | skip with a reason when the major is not `cli.MAJOR`, or say so in the test's docstring |

## C. To be clarified

| # | Question | Seen in | Options |
|---|---|---|---|
| C1 | **Cell current of the example.** With SW1 pressed a fresh CR2032 delivers 10.7 mA; maker-coverage CK-18 names 3 mA continuous, 15–30 mA in pulses. `sim.json` has no `i_max_a` for the cells, so LIM.i/cell does not run. The press is short – is it a pulse? | 17.5, sim.json; the domain power's review question on cells | `i_max_a` with the continuous value, and the finding accepted as "a press is a pulse" (D-…); a pulse limit edakit would need (a grade, or a duration in the load); leave it with a note |
| C2 | **Domains in the interview.** `edakit check` switches on what the graph suggests (`power` for a battery holder); `/edakit:new-project` does not ask for `[project] domains` | 17.5, the first line of `edakit check` | ask in the interview; leave it to the graph and say so in the skill |
| C3 | **Electromagnetically benign equipment in chapter 15.** The regulatory reviewer suggested that handbook 15.1 and 15.2 name EMVG § 2 (3) no. 2 – equipment that by its nature cannot emit relevant interference, as this board | M-6 of the walkthrough | a sentence in 15.1/15.2; leave it to the reviewer's judgement per project. Support, not legal advice: no claim to correctness, nothing legally guaranteed |
| C4 | **The "Remove Mark" choice** when JLCPCB's form still offers the order number: it changes the fab hash, so a new gate run and a new M-5 | M-5 re-check | default `mark = "remove"` for boards with `[looks]`; decide per order |

## Decisions

The owner's answers of 2026-10-31, through the form; what Claude decided itself was confirmed in one closing question.

| # | Decision |
|---|---|
| C1 | The continuous value and a reason: `i_max_a` 3 mA in the example's cell states (Jauch CR 2032 H2B, 15092025: 3 mA continuous, 15 mA pulse), LIM.i/cell accepted on BT1 as "a press is short" (the example's D-7). A pulse limit with a duration per load was more than this needs – the voltage drop is in the simulation through the cell's `r`, and above 3 mA a CR2032 loses capacity, nothing worse |
| C2 | The graph decides: the interview of `skills/new-project` asks for no domain – there is no graph yet –, and `[project] domains` is for a domain the graph suggests and the project wants off |
| C3 | Left to the regulatory reviewer per project: no sentence on electromagnetically benign equipment in handbook 15. Support, not legal advice: no claim to correctness, nothing legally guaranteed |
| C4 | `mark = "remove"` is the default of a board with `[looks]`; an explicit `mark` wins |
| B5 (Claude, confirmed) | The SMD pads of a `bom: false` part get `hand_solder_keep_mm` on their own side, the side the part sits on |
| B2, B6 (Claude, confirmed) | Stay open as live runs, in `TODO.md` |

## State after the build

Built on the branch `ccr-f80e23dc-ak6668` on 2026-10-31, test first, the suite green after every merge.

| # | State | Where |
|---|---|---|
| A1 | built: LIM.p for an LED – (Va − Vk) × I at the operating point of every scenario against `p_max_w`, derated by `derating.p`; an RGB LED per colour. The example's D1: 14.75 mW at most against 32.5 mW | `engines/sim.py` `stress()`, handbook 5.3, `tests/test_sim.py` |
| A2 | built: the fix of STRUCT.entry per case; with the library symbol cached the finding says whether the symbol agrees with the entry (the graph has another part's pins) or with the graph (the entry to be checked) | `catalog/codes.toml`, `engines/struct.py`, handbook 17.6 |
| A3 | built: offline, a signed sign-off of scope `fab` is bound to its hash, not open – "M-5 signed for fab f958… – checked by stage F" | `release/gate.py`, `requirements.py`, handbook 8.2, 17.10 |
| A4 | built: a strip without area on Freerouting's 0.01 mil grid is dropped (`flat_on_grid`); the round board keeps 50 of 66 strips, the band still covered. No live Freerouting run yet | `route.py`, handbook 7 |
| A5 | built: a tile of the polarity sheet takes in the signs GEO.mark pairs with the part; GEO.mark and the sheet share the pairing | `release/polarity.py`, `release/fab.py`, handbook 8 |
| B1 | real, built: a via is measured on its own pad (the flash at its centre); a pour or a track no longer hides a thin ring. Whether EasyEDA flashes its vias as assumed: at the next gate run with stage F | `release/fab.py`, GEO.ring |
| B2 | open: the hole unit of `footprint build` needs the live run of step 3.6 | `TODO.md` |
| B3 | real, built: `body.box` in a parts entry, GEO.silk grade `body` (warning), `silk apply` keeps labels beside a body. BT1's entry has it since, on the owner's word: [-11.05, -10, 11.05, 10] mm from the drawing QJ.BS-6 (housing 22.1 mm, cell Ø 20 mm concentric), also as the library draft `edakit/parts/C70377.json` | `pcb.py`, `silk.py`, `release/fab.py`, handbook 4.1, 7.7, 8.1 |
| B4 | real, built: FILES.order grade `tooling` (warning) – `[tooling]` on an Economic board and nothing that tells the maker | `release/order_sheet.py`, handbook 8.4 |
| B5 | real, built as decided | `route.py` `hand_joints`, handbook 7.5, 17.11 |
| B6 | open: what JLCPCB's form shows, read at the next order | `TODO.md` ("JLCPCB's order number") |
| B7 | (1) holds no more: without `silk_footprints_<b>/` the check says "run edakit silk apply", no false finding; (2) built: a page read is kept only while its page is still active, the gate closes other saved schematic tabs before the BOM. Live: whether EasyEDA reports its tab switch in time | `eda.py`, `release/fab.py`, `schematic.py`, `pcb.py`, handbook 9 |
| B8 | built: the KiCad live tests skip with a reason on another major; the CI job requires them (`EDAKIT_KICAD_LIVE: required`) | `tests/test_kicad_live.py`, `toolchain/kicad/cli.py`, `.github/workflows/tests.yml` |
| C1 | built in the example, with two gaps of edakit closed on the way: the cell's rows carry the holder, so an accept on it reaches them; the gate counts a simulation row whose finding the graph accepts as waived, not failed | `engines/sim.py`, `sim/run.py`, `release/gate.py`, handbook 5, 17.6 |
| C2 | built | `skills/new-project`, handbook 14.2, 10 |
| C3 | decided, nothing to build | – |
| C4 | built; it changes the fab hash of a board with `[looks]` and `[order]` and no `mark` – the example's at its next gate run with stage F | `config.py`, `release/order_sheet.py`, handbook 10.2, 8.4, 7.5 |

The example's circuit hash moved twice on the way – the stale accept of HINT.debounce removed in an earlier merge,
C1's limit and accept –, and the agents electrical-reviewer and regulatory-reviewer signed M-1 and M-6 again for state
`a2a6ed92…`, and once more for `e34902df…` after BT1's `body.box`. Built afterwards on the owner's word: the gate judges
a simulation finding by its severity – a warning reads warn, for the sign-off file to accept, instead of failing.
Seen and not built: a `[looks]` board without `[order]` or `[cart]` tells the maker nothing
about the mark (B4's counterpart); `silk apply` never run on a machine leaves GEO.silk unable to tell edakit's print.

