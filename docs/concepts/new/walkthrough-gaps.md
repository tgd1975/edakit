# To be checked, clarified, fixed – what the walkthrough left open

Status 2026-10-31: collected, nothing decided or built. The walkthrough of handbook 17 took `examples/coin-cell-led`
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
