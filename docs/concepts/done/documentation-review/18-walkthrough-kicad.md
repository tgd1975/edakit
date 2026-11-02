# Review of step D.5: handbook/18-walkthrough-kicad.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 500 | 500 |
| own words (prose, without tables and code) | 3276 | 3227 (−1 %) |
| mean sentence | 23.7 | 22.6 |
| test_style violations | none | none |

The chapter met every counted rule before and still does: no XPASS. It stays at the 500-line limit; the new first
paragraph and the named cross-references cost the lines that the cuts freed.

**Why not a third fewer.** The chapter is a walkthrough whose prose carries the run's numbers – currents, voltages,
part numbers, tolerances, counts – and each of them is a statement. The whole chapter is named by the automation as
"handbook 18": `edakit/toolchain/kicad/board.py:405`, the docstrings of `tests/test_wrong_judgements.py:115`,
`tests/test_pcb.py:243`, `tests/test_fab_run.py:1223`, `tests/test_switched_supply.py:1`, `:81`,
`tests/test_part_import.py:223`, `tests/test_kicad.py:204`, `:283`, `tests/test_walkthrough_kicad.py:1`; 18.10 to
18.12 by `examples/blinker-555/README.md:36`; the file by `examples/blinker-555/edakit.toml:2` and
`hardware/requirements.toml:7`, `:14`. `tests/test_walkthrough_kicad.py` holds the quoted numbers to the example, so no
code block, quoted output or command changed (checked: all 20 code blocks, every table row and image line identical to
HEAD). What could go without a statement going – restatements of a code block, of an output or of another section, and
asides – went; the statements won.

## Per section

- **Opening** – new first paragraph: for whom (drawing in KiCad, cells behind a power switch, an IC through every step)
  and what after. "This chapter takes the board … the way chapter 17 took the coin cell board" shortened to "tells only
  what differs from the coin cell board of chapter 17". "(chapter 16)" → "(KiCad as the tool chain, chapter 16)",
  "(3.1)" → "(the graph's format, 3.1)". The state line is now a block quote `> **State 2026-10-31:** …`; "on a machine"
  and "As in chapter 17" dropped.
- **18.1** – table unchanged. "(2.2, 16.2)" → "(install, 2.2; KiCad's setup, 16.2)"; "In this run" dropped.
- **18.2** – "as in 17.2" → "as in chapter 17 (set up, 17.2)"; "the owner's own use only" → "your own use only"; "a
  reader who builds the board … needs a review M-6 of their own (chapter 15)" → "If you build the board … that is
  another purpose and needs a review M-6 of its own (the regulatory review, chapter 15)". The disclaimer stays here.
- **18.3** – "the owner's word" → "your decision"; "Two of the numbers did not survive the run – R-1 in 18.6, R-4 in
  18.8" → "Two numbers did not survive the run: R-1 changed with the checks' findings (18.6), R-4 with the reviews
  (18.8)".
- **18.4** – one sentence merged ("U1 is the LMC555, its entry behaviour `logic`"); "(5.1)" → "(the netlist, 5.1)",
  "(18.8)" → "(the reviews, 18.8)"; "two pegs of its frame" → "two frame pegs".
- **18.5** – "(3.1)" dropped from "The graph is TOML from the first line" (the opening names it); one sentence
  reordered; "(18.13)" named.
- **18.6** – "In 17.6 the LED blocked by itself" → "On the coin cell board the LED blocked by itself (17.6)"; the blink
  rate's first two paragraphs merged, the long sentence on U1's thresholds split; a re-wrap of the 680 kΩ paragraph.
- **18.7** – "the 10 nF at CV was one of them, and a Basic 10 nF … took its place" → "a Basic 10 nF in 0805 (C1710)
  replaced the one at CV".
- **18.8** – "each in a context of its own" dropped (18.1 says it); "one finding was important" → "one finding
  mattered"; "(5.1)" named. **The second regulatory disclaimer (M-6 bullet) removed** – CLAUDE.md asks for it once per
  page, and 18.2 has it (see Assumptions).
- **18.9** – "as in 17.10" → "as on the coin cell board (17.10)"; a comma added.
- **18.10** – "(16.3)" → "(the KiCad project, 16.3)".
- **18.11** – Placement: the aside "– moved by hand 5 mm to the left, and …" made a sentence of its own; "(7.4)" →
  "(the placement plan, 7.4)". Routing: the one 70-word sentence of the three tries split in four. The layout review:
  "One hole lies under the holder, which is fitted after the assembly." dropped – the `[tooling]` comment below says it
  ("the second under BT1's body: the holder is fitted after the assembly"); "of our own" → "of your own".
- **18.12** – "(16.6)", "(16.3)", "(8.4)" named; the five runs' sentence split; "R-3 and R-4 passed on their rows; R-1
  and R-2 wait for the acceptance." dropped – the output above it ("requirements: 2 passed, 2 open after the export")
  and 18.9 say it. "a walkthrough, no boards ordered – your decision, as the order is in chapter 17" → "no boards
  ordered: the order is your decision, and chapter 17 shows it".
- **18.13** – the restated symptoms dropped where the earlier section tells them: "VDD sat at −0.84 V on 1 pA into the
  simulator's 1 TΩ shunt" (in 18.6, now linked), "`r_out_ohm` of a logic part takes [min, typ, max] at the spread
  corner" (in 18.8; here "takes a range now"), "Freerouting left two GND pads room for one spoke each" reworded with
  the link to 18.11. Sentences quoted by test docstrings kept word for word ("KiCad nets a pin its schematic marks
  no-connect as …", the BBox and `body.box` numbers). "Open, noted for later" split into sentences, "(8.7)" →
  "(requirements, 8.7)".

## To the history file

Nothing (`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/18.md` says why).

## Findings

- "Open, noted for later" in 18.13 lists five open points (requirement-ID counting in sign-off notes, EasyEDA wording
  in `route all` and in stage S on KiCad, `pcb plan` and `hand_solder_keep_mm`, the square notch in KiCad pours, the LED
  model's ideality). By the style guide, a smaller extension or a fix is `TODO.md`'s, not the site's; whether they
  are in `TODO.md` was not checked. Left in the chapter.
- The stage S row in 18.12's protocol excerpt reads "EasyEDA schematic = graph" on a KiCad run – the chapter itself
  names that as open; the quoted output is not changed.

## Assumptions

1. The second disclaimer (18.8, M-6 bullet: "Its result is support, not legal advice: it claims no correctness, and
   nothing in it is legally guaranteed.") removed, the first (18.2) kept. CLAUDE.md: "it says once". If the owner wants
   it at every M-6 result, it goes back word for word.
2. "your own use only" for `private`: the purpose of the example's builder is the reader's own case too; the sentence
   after it covers giving away or selling.
3. Restatements of a code block, of a quoted output or of another section of the same chapter are cut even in a chapter
   the automation names as a whole – the statement stays in the chapter, at the place that owns it.
4. 18.13 stays: it is the walkthrough's record of what the run changed, referred to from every section ("closed on the
   way, 18.13"), not edakit's history for chapter 13.
5. The state line keeps its date (2026-10-31): it dates the outputs and the tool versions, which the test holds.
6. Internal cross-references "(18.13)" are left bare in some places where the sentence names the subject already
   ("closing a gap of the KiCad chain …"); the external ones all name their subject now.
