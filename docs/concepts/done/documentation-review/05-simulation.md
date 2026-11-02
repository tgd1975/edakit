# Review of step D.5: handbook/05-simulation.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 552 | 648 |
| own words (prose, without tables and code) | 7170 | 7148 (−0.3 %) |
| mean sentence | 36.6 | 30.3 |
| test_style violations | sections 2 (192 and 252 lines without a subheading), paragraphs 25 (up to 218 words), chapters 1 (552 lines) | chapters 1 (648 lines) |

`tests/test_style.py` now passes `sections` and `paragraphs` for the chapter (XPASS strict): the chapter can leave
those two sets of `RED`. It still fails `chapters`.

**Why not a third fewer, and why longer.** Every numbered section but 5.5 is named from outside: 5.1, 5.2, 5.3 and
5.4 by 30 places in `edakit/catalog/codes.toml`, `edakit/blocks/eurorack-power.json` and the skills
`circuit-design`, `own-part`, `new-project` and `pcb-round`; the file itself by `edakit/sim/netlist.py:80`. In such a
section no statement may leave, and the chapter is almost nothing but statements – key names, defaults, numbers from
datasheets and examples, conditions. On top of that, long runs of its wording reappear in code and data: the
docstrings of `edakit/sim/netlist.py`, `strip.py`, `spread.py`, `ac.py`, `run.py`, the engine `edakit/engines/sim.py`,
the why texts of `codes.toml`, the skill `circuit-design` and chapter 4 share 6- to 20-word phrases with about 90
places of the chapter (a 6-word n-gram search). Under rule 5 of the brief those phrases stayed as they were. What could
go – asides, "as before", a duplicated list of powers, joined sentences – was outweighed by what the brief asks to add:
a first paragraph, subjects for the cross-references (about 20 words). The statements won.

The lines grew by 96 because the structure rules cost lines: 19 new `###` headings (38 lines) and about 30 long
paragraphs split (one blank line each), plus the fault cases as a list. The two tables whose cells are paragraphs (the
behaviour models, the spread corners) stayed tables: as entries they would add about 60 lines and break the
120-word rule eight times. 500 lines are not reachable without dropping statements.

## Per section

- **(new) first paragraph** – for whom: "when you set up a board's scenarios or a part's behaviour model"; the existing
  sentence on what `edakit sim` does follows it unchanged.
- **Intro, why DC first** – "Why DC operating points first:" → "DC operating points come first because"; the
  paragraph split in two (static errors; supply changes and switching). The second sentence ("A resistor that cooks …
  a regulator without headroom at the low end of the USB voltage …") kept word for word – `codes.toml` uses it.
- **Intro, severities and acceptance** – the aside "– a new code or grade starts as one –" became a sentence of its
  own; "(8.3)" → "(the decision, 8.3)", "(3.4)" → "(working rules, 3.4)". "A scenario's status follows its rows" kept.
- **5.1 How the netlist is built** (named by `codes.toml` lines 588, 602, 660, 1745, 1752, 1759, 1765, 1772, 1779,
  `eurorack-power.json:157`, `skills/own-part/SKILL.md:93`, `skills/circuit-design/SKILL.md:115`). No statement left
  the section; eight `###` headings added by topic, the items in their old order: Parts from the graph, Supplies,
  Nets, cables and off-board loads, LED strips, Behaviour models, Constant-current LED drivers, Other models and model
  rules, Your own models.
  - Long list items split into items of their own: the 0 Ω bridge and the DC-bias capacitor out of the first item;
    the relay, the buzzer and the potentiometer out of the switches item; the multi-rail connector out of the supplies
    item; the MCU's `i_core_min_a` out of the `i_min_a` item; the wire current out of the cable item.
  - The backfeed item reordered so that its last clause is no longer two parentheses in a row: the NiMH example now
    sits with `i_charge_max_a`, "both are `criteria.blocking_max_a` (1 mA) unless set" refers to `i_back_max_a` and
    `i_charge_max_a` as before, and the cell's `i_max_a` (LIM.i/cell, accepted on the holder, the walkthrough's D-7)
    is a sentence of its own – checked against `edakit/engines/sim.py` lines 503–517.
  - The LED strip item became four paragraphs under "LED strips" (model; feeds and chaining; LIM.range/strip and the
    currents; the Pololu example and the model's two limits). "(chained: …)" → "– chained: … –".
  - The adjustable regulator, the asynchronous boost, the constant-current buck and the PhotoMOS/ESD paragraphs split
    where they passed 120 words; the sentences with the TI quote, the dim levels and the pull-up kept word for word
    (`netlist.py` shares them).
  - The behaviour-model table, the plugin example and the LIM.range/cc list unchanged.
- **5.2 Scenarios** (named by `codes.toml` lines 222, 314, 1562, `skills/circuit-design/SKILL.md:116, 121`,
  `skills/new-project/SKILL.md:110`, `skills/pcb-round/SKILL.md:112`, and the glossary's link to `#52-scenarios`). No
  statement left the section. Nine `###` headings; the four bold run-in titles "The spread of the transistors",
  "Routed copper", "Transient runs", "AC runs" became `###` headings with the same words (the catalog names "5.2
  (transient runs)"), five new ones: Several sources, Fault cases, Ambient, cells and touch, What a load expects.
  - Moved inside the section: the sentences on `ambient_c`, `ambient_min_c` and battery cells, which stood at the end
    of the fault-scenario paragraph, now open "Ambient, cells and touch"; the `"matrix": false` sentence opens "Fault
    cases" (it was the last sentence of the `combine_sources` paragraph and speaks of fault cases).
  - The intro sentence now reads "A board's scenarios are in `hardware/sim.json`"; the Christmas bell's file stays as
    the example of a USB-powered module with a servo.
  - The code block `"spread": ["min", "max"]` became inline code in the sentence that explains it.
  - The three fault kinds became a list; the transient run's "(LIM.range; the limits of `expect` are LIM.v on a net and
    LIM.i on a source)" moved to the sentences they belong to.
  - Example paragraphs (the MMBFJ201 booster, the copper drop, the strip feeds, the pickup resonance) kept with every
    number: they are statements of the named section, and several are held by tests.
  - "handbook 18" in the load's `expect` → "the KiCad walkthrough, chapter 18".
- **5.3 Checks** (named by `codes.toml` lines 220, 222, 256, 273, 286, 306, 314, 329, 433, 447, 621, 635,
  `tests/test_contacts.py:121`). No statement left the section. Two `###` headings (Power, heat and touch; Levels and
  LEDs) to keep it under 80 lines; bold titles "**LEDs.**" and "**LEDs on a sink.**" added to the two LED paragraphs.
  - The junction temperature's list of powers – a repeat of the list under **Power** – became "as for LIM.p, a diode's
    VF × IF and a MOSFET's body diode included (ngspice counts it in the drain current)". The list under **Power** is
    unchanged (its wording is in `codes.toml`).
  - The paragraph on the reversed LED kept word for word (`codes.toml:635` quotes it).
  - The introduction to the generated table unchanged; the generated table untouched.
- **5.4 Track widths from the simulation** (named by `codes.toml:860`) – split in two; "The voltage drop GEO.width
  shows is an upper bound" → "GEO.width shows the voltage drop as an upper bound"; "(7.5)" → "(routing with
  Freerouting, 7.5)", "(5.2)" → "(routed copper, 5.2)".
- **5.5 Every check seen red** – unchanged.
- **Cross-references** – every parenthesised section number now has a subject before it or inside the parenthesis
  ("(the graph's cables, 3.1)", "(parts fields, 4.1)", "(rule checks, 3.3)", "(what the checks found, 17.6)"),
  except inside the two tables, which were not edited.

## History

Three phrases of "as before" left the chapter (5.1 `i_min_a`; 5.2 spread; 5.2 routed copper); they are listed verbatim
in the history file for chapter 13, though none needs a place there. Nothing else in the chapter is history.

## Findings

Sentences that look wrong or loose against the code – not changed:

1. **5.1, adjustable regulator:** "with `i_load_min_a` every scenario loads the regulator at least that much
   (LIM.range/min_load …)". `edakit/engines/sim.py` (around line 533) does not add a load; it checks that the
   regulator's output current reaches `i_load_min_a` ("output current at least the minimum load", LIM.range, grade
   `min_load`). The sentence reads as if the simulation added the load. Suggested: "every scenario must load the
   regulator at least that much".
2. **Intro:** "transient runs (5.2) follow the supply over time and LIM.v judges them" – a transient run is judged by
   LIM.v on a net, LIM.i on a source and LIM.range for an MCU's minimum (5.2, transient runs). "LIM.v judges them" is
   short for that; a reader may take it as the only code.
3. **5.2, spread table (not edited):** the cell of `ic` of behaviour `logic` ends "(handbook 18)" – inside the
   handbook "chapter 18" or "the KiCad walkthrough (18)" would fit. It also carries a short story ("one number hid the
   555 blinker's current from fresh cells"), which the style guide would send to chapter 13.
4. **Source texts that echo the chapter:** the docstrings of `edakit/sim/netlist.py`, `strip.py`, `spread.py`, `ac.py`,
   `run.py` and the why texts in `edakit/catalog/codes.toml` repeat the chapter's sentences almost word for word. As long
   as they do, the chapter cannot be condensed without the two drifting apart. Whether the code should keep its own
   wording or point to the handbook is the owner's call.

## Assumptions

1. **Shared phrases kept word for word.** Every sentence that shares a run of six or more words with code, data, a
   skill, a test or another chapter kept that run unchanged (rule 5 of the brief); this is why the chapter lost almost
   no words. A looser reading – a docstring that only mirrors the handbook is no reader of it – would allow about
   10–15 % more.
2. **The chapter is longer than before (648 lines against 552)** – the 80-line and 120-word rules were judged worth
   more than the 500-line rule, which cannot be met here without dropping statements.
3. **The two paragraph-cell tables stayed tables** (behaviour models in 5.1, spread corners in 5.2) and were not
   edited – both sit in named sections, and as entries they would break the 120-word rule.
4. **Moves inside 5.2** (ambient and cells to "Ambient, cells and touch", `"matrix": false` to "Fault cases") – read as
   allowed by "no statement leaves the section"; statements stay in 5.2.
5. **Bold run-in titles became `###` headings** in 5.2 (same words), new bold titles were added in 5.3; the bold titles
   of 5.3 that existed stay bold.
6. **"the reference circuits"** in the AC runs stays – it means `tests/reference.py`, not the reference project.
7. **The IEC 62368-1 touch limits (5.2)** were left without a "not legal advice" line: the chapter quotes a standard's
   temperatures as a project setting, not as regulatory advice. If the owner reads it as regulatory content, chapter 15
   is the place that says it once.
8. **Cross-reference subjects** were chosen from the target headings: "the decision" (8.3), "working rules" (3.4),
   "rule checks" (3.3), "parts fields" (4.1), "the graph's cables / format" (3.1), "routed copper", "the touch limit",
   "several sources" (5.2), "heat and touch", "LEDs on a sink", "checks" (5.3).
9. **"For you when …"** as the first paragraph is one sentence, followed by the old first sentence – the chapter's
   readers are the person or session writing `hardware/sim.json`, which is how `handbook/README.md` describes it ("you
   set up scenarios or a behaviour model").
