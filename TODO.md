# TODO

Open work that needs the owner's computer, a maker or the owner's word. The state of every step is in the concepts
and plans the sections name; this list is what is left to do of them, in the order it can be done. No item is deleted.

**Layout.** Every item, in every section, open or closed, is a line with a checkbox and an ID unique in this file,
counted up and never reused – whoever adds an item takes the next free ID and counts it up here. Next free ID: TD-152.

- Open: `- [ ] TD-<n> - **Title:** what and why.` – a step's own name after the dash (`- [ ] TD-31 - **D.4** …`).
- Done: ticked, the commit that did it, the date at the end, moved to [Closed todos](#closed-todos), newest first –
  by whichever session learns it; a dropped one says so: `- [x] TD-<n> - **Title:** what came of it (commit). [date]`.
- For the owner: what only the owner can do – an account, a payment, an OK, hardware in hand, a click in Claude
  Code – goes into a section "For the owner" at the top, one line each, the session at the end:
  `- [ ] TD-<n> - **What:** command or link – why. *(session)*`. An item further down that waits for the owner
  stays where its step is.
- One item, one piece of work: one thing to do, by one hand, at one time, done when one statement is true – no
  collecting tank. Short and plain: what, why, where; history and details stay in the file the section names. A
  part that waits for something else or is someone else's is an item of its own.
- Headings group open items; once none is left under one, the heading and its text go, and it comes back with the
  next item that belongs there.

**Taking an item.** Several sessions work on edakit at once. Before a session starts an item, it lists the others
(`ListAgents`, `git worktree list`), asks each running edakit session which item it holds, and takes one that nobody
holds and whose files no open branch touches – the concepts' tables name each step's files. An item that waits for
another (W.4 after W.2) is agreed with the session holding that one and merged after it. Each item gets a worktree of
its own beside the main clone, named for it (`../edakit-w4`, branch `wired-w4`), so `git worktree list` shows who
holds what; the main clone belongs to whoever has it checked out, and its uncommitted changes are not anyone else's
to touch.

## For the owner

- [ ] TD-108 - **A photo of the delivered tree:** one picture of the lit tree in its hill into pytree's `docs/img/` –
      it replaces the render on `docs/projects/pytree.md`. *(edakit-ce)*

## The parts order ([docs/concepts/done/parts-order.md](docs/concepts/done/parts-order.md))

- [ ] TD-144 - **Live run of `combine`:** the skill cart's mode `combine` at the next JLCPCB order whose basket has
      LCSC lines – the warehouse address at JLCPCB's checkout, after the payment the tick at LCSC's checkout and its
      methods in `shipping.json`; what it finds into `lcsc.toml` and handbook 8.4. *(edakit-5e)*

## Parts on hand ([docs/concepts/done/parts-on-hand.md](docs/concepts/done/parts-on-hand.md))

- [ ] TD-147 - **Step 3, the live run:** the next parts order with your inventory named in `edakit.local.toml` – the
      carts shortened by what is on hand, `hand_assembly.md` naming what to take; what the run finds goes into handbook
      8.4. Waits for an inventory file of yours (`edakit inventory template FILE`). *(edakit-87)*

## The explorative DSL ([docs/concepts/new/circuit-dsl-toolchain.md](docs/concepts/new/circuit-dsl-toolchain.md))

- [ ] TD-150 - **Designators that start with a digit:** `edakit graph convert --to circuit` refuses the two GuitarML
      open designs (`tests/open_designs/guitarml-*`), whose designator `9v1` the language reads as no name ("unknown
      key '9v1.Pin_1'"). The language needs a form for such a designator, and the converter writes it; a test converts
      both designs. Only with `[beta] dsl = true` (decision 51). *(gracious-fermat)*
- [ ] TD-151 - **Empty entries in a converted graph:** `graph convert --to circuit` refuses the other eight open designs,
      since `nc: []`, `layout: {}` and `locks: {}` do not read back and the converter's own check finds the
      difference. An empty entry and a missing one mean the same, so the conversion carries them over or the check
      treats them alike; a test converts every open design. Only with `[beta] dsl = true` (decision 51).
      *(gracious-fermat)*

## What edakit needs from EasyEDA Pro and easyeda-mcp-pro ([upstream/README.md](upstream/README.md))

E-1 to E-17 on EasyEDA Pro and M-1 to M-10 on easyeda-mcp-pro, checked live on EasyEDA Pro 3.2.209 and posted on
2026-11-01; what each asks and where it stands is in upstream/README.md – the items here say only what is left to do.

### Waiting for upstream

Nothing to do until there is an answer or a release; whichever session learns of one takes it.

- [ ] TD-36 - **EasyEDA, #45 to #52 and our comments to #36 and #38:** answer questions; when a release fixes one,
      check it live, take it up and say so in upstream/README.md. EasyEDA's first answer is often "update to the latest
      version".
- [ ] TD-140 - **M-11, easyeda-mcp-pro #864 and #865:** answer questions; when a release takes the fix, raise the
      pin, check it live on pytree's `tree` with `layout_tree` open, and drop the closing of the other schematics in
      `schematic check` and stage S. *(edakit-7b)*

## Closed todos

- [x] TD-149 - **OK for #332 (the LESD5D5.0CT1G is a bidirectional TVS):** given; merged as edakit 1.1.16 (#332).
      *(edakit-c6)* [2026-11-03]
- [x] TD-145 - **Is the LESD5D5.0CT1G bidirectional?** Yes – symbol p. 1 and I–V curve p. 2; `values.tvs
      "bidirectional"` in both entries, the DevKitC's findings unchanged (LIM.v on D6 only, no PATH.reverse); #332, its
      OK is TD-149. *(edakit-38)* [2026-11-03]
- [x] TD-148 - **OK for #326 (step 10, parts you solder yourself):** given; merged (#326, no version). *(edakit-87)* [2026-11-03]
- [x] TD-143 - **The 23 lines of the live run in LCSC's cart:** settled by the owner in LCSC's cart. *(edakit-5e)*
      [2026-11-03]
- [x] TD-146 - **OK for #321 (parts on hand):** given; merged as edakit 1.1.14 (#321). *(edakit-87)* [2026-11-03]
- [x] TD-142 - **OK for #310:** given; merged as edakit 1.1.13 (#310). *(edakit-5e)* [2026-11-03]
- [x] TD-133 - **A charger's status output in the simulation:** the charger model drives STAT – the Micro-Lipo's LEDs as
      on the board (#309, edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-132 - **A bidirectional TVS:** `values.tvs: "bidirectional"` – ADLSC's D4 gone (#309, edakit 1.1.12).
      *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-131 - **A ground tied to mains:** LIM.hazardous/ground names it – the ESPurna-H's R42 found, judged real;
      handbook 19.9 names what stays unseen (#309, edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-130 - **A mains terminal as a supply input:** connector roles `line`, `neutral` in `[supply] inputs` –
      PATH.unfed on the HLK-PM01 gone (#309, edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-129 - **AC nets and AC ratings:** net `ac` and `v_rms_max_v` – the ESPurna-H's six LIM.v known gaps gone (#309,
      edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-128 - **A varistor kind:** kind `varistor` (VRMS, VDC) – the ESPurna-H's S10K250 now found below 230 V + 10 %,
      judged real (#309, edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-127 - **Board copper is nothing to buy:** `own.what: "copper"` – no supplier, compliance fact or EasyEDA device
      asked; 33 findings of SJ1 and the pads gone (#309, edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-126 - **A trimmer is not a panel pot:** `values.adjust: "trimmer"` leaves it out of REQ.value/switch – the Fuzz
      Face's TRIM2 gone (#309, edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-125 - **A low-side reverse-polarity MOSFET as a block:** `[reverse] cuts` – an N-MOSFET in the ground return
      takes a reversed source off ground; ADLSC's 18 known gaps gone (#309, edakit 1.1.12). *(ccr-de7c0e28)*
      [2026-11-03]
- [x] TD-124 - **A connector passes no reversed source:** a connector tolerates a reversed source in `paths.toml
      [reverse]` – the Micro-Lipo's four known gaps gone (#309, edakit 1.1.12). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-111 - **Live run at the next parts order:** mode `parts` ran on 2026-11-03 – four projects, 23 lines into
      LCSC's cart, nothing ordered; the profile recorded and the weight's "1,500g" read (#310); `combine` split off as
      TD-144. *(edakit-5e)* [2026-11-03]
- [x] TD-141 - **OK for #305:** given; merged as edakit 1.1.10 (#305). *(edakit-5e)* [2026-11-03]
- [x] TD-138 - **Step 10 ends with the assembled board:** JLCPCB's preview of TD-137 at M-2 in
      `docs/steps/10-order-the-board.md` (#300). *(edakit-f9)* [2026-11-03]
- [x] TD-137 - **A screenshot of JLCPCB's assembly preview of coin-cell-led:** Gerber, BOM and CPL of the gate run of
      2026-11-01 uploaded in the owner's Chrome up to Component Placements, nothing into the cart; into
      `examples/coin-cell-led/docs/jlcpcb_assembly_main_top.png` (#300). *(edakit-f9)* [2026-11-03]
- [x] TD-136 - **Step 9 shows the routed board:** `board_main_layers.png` under the paragraph on placing and routing in
      `docs/steps/09-lay-out-the-board.md` (#300). *(edakit-f9)* [2026-11-03]
- [x] TD-135 - **The layers picture of coin-cell-led:** drawn by the gate run of 2026-11-01 with stage F, copied into
      `examples/coin-cell-led/docs/` – no owner step needed (#300). *(edakit-f9)* [2026-11-03]
- [x] TD-122 - **The bell in the language, in its own repository:** dropped on the owner's word – the DSL is a
      beta on its own branch (decision 48), the bell need not move to it now. *(friendly-mccarthy)* [2026-11-03]
- [x] TD-139 - **OK for #291:** given; C70374 and C22355741 signed, merged as edakit 1.1.7 (#291). *(edakit-56)*
      [2026-11-03]
- [x] TD-109 - **M-11 (easyeda-mcp-pro's net reading takes a net flag of another open schematic):** posted on the
      owner's word as #864 and #865, from the fork's `fix/net-read-one-page` rebased onto 1.8.1's main (#294); the
      wait for the release is TD-140. [2026-11-03]
- [x] TD-134 - **Delete the branches a cloud session cannot delete:** deleted by the owner – the four branches
      checked first: both `claude/…` contained in main, both `notes/…` landed on main another way. *(ccr-de7c0e28,
      edakit-4f)* [2026-11-03]
- [x] TD-110 - **OK for #265:** given; merged as edakit 1.1.5 (#265) – the parts at LCSC (`edakit order check`,
      ORDER.basket) and the combined shipment; the live run is TD-111. *(edakit-4f)* [2026-11-03]
- [x] TD-123 - **OK for chapter 19 and the four open designs:** given; merged as edakit 1.1.4 (#281, `f42bde3`) with
      merge.py and notes.py through REST; the concept moved to `done/`. *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-117 - **VV.1–VV.4 Handbook chapter 19:** `handbook/19-verification.md`, its lists generated from the tests'
      data, the countable admission rules as tests – edakit 1.1.4 (#281). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-118 - **A WLED controller as an open design:** `tests/open_designs/atoomnetmarc-adlsc/`, Apache 2.0, 36
      findings judged – edakit 1.1.4 (#281). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-119 - **A Fuzz Face as an open design:** `tests/open_designs/whbeers-fuzz-face/`, CC0 1.0, a silicon 2N3904
      for the germanium pair, 11 findings judged – edakit 1.1.4 (#281). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-120 - **A relay board with an HLK-PM01 as an open design:** `tests/open_designs/espurna-h/`, CC BY-SA 4.0,
      21 findings judged – edakit 1.1.4 (#281). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-121 - **A LiPo charger as an open design:** `tests/open_designs/adafruit-microlipo-usb-c/`, CC BY-SA 3.0, 27
      findings judged – edakit 1.1.4 (#281). *(ccr-de7c0e28)* [2026-11-03]
- [x] TD-113 - **OK for the circuit language:** given; merged as edakit 1.1.3 (#279) – T.1 to T.27, the decisions 1
      to 48 confirmed; circuit-dsl.md, its language and its plan moved to `done/`. Withdrawn by #287 (1.1.6) on the
      owner's word: a beta on the branch since, the concepts back in `new/`. *(friendly-mccarthy)* [2026-11-03]
- [x] TD-116 - **The job sysml:** run on the branch by `workflow_dispatch` – 4 passed, read with the standard
      library 2025-12 that systree loads (decision 45); main runs it with every merge. *(friendly-mccarthy)*
      [2026-11-03]
- [x] TD-115 - **The bell in the language, the test:** T.17's test run with `BELL_ROOT` against the bell's `cfb0ab0` –
      all five configurations canonically equal but for the LED step's additions, esp32 and esp32tht written
      (decision 43, `28b5c1c`); its own conversion is TD-122. *(friendly-mccarthy)* [2026-11-03]
- [x] TD-114 - **The three evals of the language:** run once each with Sonnet 5.5 – 1.00 each, after two graders'
      regexes were made JavaScript (`9d1289e`); the table in `evals/README.md` (decision 45). *(friendly-mccarthy)*
      [2026-11-03]
- [x] TD-112 - **OK for #267:** given; merged as edakit 1.1.2 (#267) – the newcomer's gaps closed;
      documentation-newcomer.md moved to `done/`. *(edakit-df)* [2026-11-02]
- [x] TD-105 - **E-18 (a pin on a second net while another schematic of the project is open):** checked live on
      EasyEDA Pro 3.2.209, still the newest, and against the docs – not EasyEDA's, nothing to report there: a V_LED flag
      of `layout_tree` sits on the end of the template's wire from U4.11, and easyeda-mcp-pro takes the flags of every
      open schematic but the wires of one; it goes upstream as M-11 (TD-109, branch `td105-m11`). [2026-11-02]
- [x] TD-82 - **pytree's pictures:** picked by the owner on 2026-11-02 – the board from the ordered release
      20261101-225744, the tree in its hill (a photo replaces it, TD-108), the copper review's before/after; the gift's
      words stand before Christmas (#257). [2026-11-02]
Done or dropped, newest first, each with its date and the commit that closed it. What closed before 2026-11-01 is
taken from the history of this file; an item rewritten on its way is listed once, in its last form.

- [x] TD-107 - **The bridge extension 1.8.0:** swapped by the owner, the old servers ended; #250's live checks on
      coin-cell-led green (doctor, create with `bom: false`, pours, DRC, gate S/L/F, export). [2026-11-02]
- [x] TD-84 - **easyeda-mcp-pro, #818 and #819** (M-10): #819 released in 1.7.0; `fill` rebuilds a net's pours in one
      call again, live on coin-cell-led (#250, edakit 1.1.0). [2026-11-02]
- [x] TD-26 - **easyeda-mcp-pro, #792 to #805** (M-1 to M-5, M-7, M-9): released in 1.7.0; edakit pins 1.8.0, both
      patches gone, the workarounds taken up, checked against the source and live (#250, edakit 1.1.0). [2026-11-02]
- [x] TD-106 - **#117 on `tree` (pytree):** run by pytree-29 – with #232 the check differed before and after the
      gate; the cause was the board's schematic `layout_tree` left open, not the save. Fixed in #256 (edakit 1.0.14),
      live on `tree`: with `layout_tree` open the check matches. [2026-11-02]
- [x] TD-104 - **A picture of the routed board for the walkthroughs:** `board_main_top.png` of a gate run in both
      examples' `docs/` – coin-cell-led from the EasyEDA run 20261101-200611, blinker-555 from `gate --eda` with KiCad
      10 –, shown in handbook 17.11 and 18 after the silkscreen (#246, edakit 1.0.10). [2026-11-02]
- [x] TD-99 - **Decide on parts on hand (PartsLedger):** decided in a decision round – movements 1 and 2, edakit only
      reads the bin; `[project] bin`; need plus spares; siblings shown, kits as data; profiles partsledger, csv, xlsx;
      the name open while it is a concept (`docs/concepts/done/parts-on-hand.md`, "Decisions"). [2026-11-02]
- [x] TD-83 - **The findings of the chapters' reviews:** fixed or decided (#248, edakit 1.0.8) – the handbook follows
      the code, the sources name the sections they cite, the catalog names pytree and the bell, 14.2's engines table
      generated, 8.4 "you order and pay"; what the reviews left stays left. *(edakit-b7)* [2026-11-02]
- [x] TD-103 - **The eval case first-circuit, three faults** fixed (#236): the prompt names `site/…`, the plugin's
      handbook as a twin, edakit's code off limits, the skills to be used, no network; `few-pages` counts Read calls
      from the trace; judges on the graph file and the trace, a regex on the DONE line; four graders catch reads of
      `edakit/`. Two runs with it, 0.875 each, in the concept's status line. *(edakit-c1)* [2026-11-02]
- [x] TD-102 - **Run the eval first-circuit in a cloud session:** done on 2026-11-02 as the user `eval` with
      `TMPDIR=/srv/evaltmp` – 0.875, 0.88 USD, 32 turns, Bash wrote the workspace; the result in the status line of
      `docs/concepts/done/documentation-newcomer.md`. Two runs the same day did not count (root 0.33, `eval` 0.83):
      Bash read-only, the workspace under `/tmp`, which the harness denies. *(edakit-c1)* [2026-11-02]
- [x] TD-98 - **N.5** The newcomer's test: the eval case `evals/first-circuit` run once in a cloud session (TD-102) –
      0.875, thirteen pages opened, the gaps of its `MISSING:` line – into the concept's status line. *(edakit-c1)*
      [2026-11-02]
- [x] TD-101 - **`sudo apt install socat`:** done; the eval first-circuit runs on this machine. *(edakit-c1)*
      [2026-11-02]
- [x] TD-100 - **OK for #222:** given; merged as edakit 1.0.1 (#222). *(edakit-c1)* [2026-11-02]
- [x] TD-97 - **N.4** The handbook declared complete: its index's first line, "The short way" in each chapter's first
      paragraph (#222, edakit 1.0.1). *(edakit-c1)* [2026-11-02]
- [x] TD-96 - **N.2** The steps: `docs/steps/` with its index and ten pages in the tabs "A circuit" and "A board",
      `tests/test_steps_pages.py`, the style guide's section and its counts (#222, edakit 1.0.1). *(edakit-c1)*
      [2026-11-02]
- [x] TD-57 - **The real cost of the first order:** done on pytree's paid order of 2026-11-02 – the order page read
      into `actual.json`, `edakit cart actual` (branch cart-confirm, #220) wrote `actual.md`, the project's fee table
      `hardware/fees/jlcpcb.json` (setup, stencil, the PCB price for 100 × 170 mm) and the order record; a fee whose
      count the page lacks is named, not written. Two fixes on the way: an amount printed -$10.00, an order without
      a number. *(edakit-80)* [2026-11-02]
- [x] TD-95 - **OK for #215:** given; merged without a version (#215, 1d177e1). *(edakit-96)* [2026-11-02]
- [x] TD-94 - **N.1 + N.3** The site's navigation as tabs by reader with "Inside edakit", the start page's first screen,
      How it works without "The words", the glossary's ten words first, the budgets in style.md and test_style.py; the
      documentation concept moved to `done/` (#215, 1d177e1). *(edakit-96)* [2026-11-02]
- [x] TD-93 - **Decide on the documentation for a newcomer:** decided in a decision round – six of seven as
      recommended, the newcomer's test the eval alone; N.1 and N.3 started the same day (TD-94). *(edakit-96)*
      [2026-11-02]
- [x] TD-81 - **Review the documentation as built:** the judgement call that mattered – rule 5, every statement stays –
      decided with documentation-newcomer.md's decision 7: kept strict, the handbook is the assistant's and the look-up
      reader's; 1.0.0 was the owner's word at the first order (TD-49); documentation.md moves to `done/` with TD-94's
      branch. *(edakit-96)* [2026-11-02]
- [x] TD-49 - **V.6** 1.0.0 released on the owner's word at the first order – pytree's tree and the bell's tht and
  esp32tht at JLCPCB, the milestone in handbook 13.7 (#210, 72bf30b). *(edakit-4b)* [2026-11-02]
- [x] TD-92 - **OK for #194:** given; merged as edakit 0.6.0 (#194, 78ae7d7). *(edakit-6a)* [2026-11-02]
- [x] TD-89 - **The LED model's ideality:** `values.vf_vs_if`, points of the datasheet's IV curve, sets it; 2 without,
  `edakit part lint` holds the points to their form (#194, 78ae7d7). [2026-11-02]
- [x] TD-88 - **Pours around a tooling hole on KiCad:** the pour follows the outline, a rule area keeps each hole's keep
  circle free; GEO.pour and route's computed pours measure that area on both tool chains (#194, 78ae7d7). [2026-11-02]
- [x] TD-87 - **`pcb plan` and `hand_solder_keep_mm`:** held since 3187f9f; the test came with #194 (78ae7d7).
  [2026-11-02]
- [x] TD-85 - **A sign-off note as evidence:** the owner's decision – only an ID after "requirements met:" counts; built
  with the agents, skills and handbook 8.7, edakit 0.6.0 (#194, 78ae7d7). [2026-11-02]
- [x] TD-91 - **OK for #186, the feature proposals #153 and #113:** given, merged as edakit 0.5.0 (05cd313);
      #153 and #113 closed. [2026-11-02]
- [x] TD-86 - **Messages on KiCad:** closed by 27b86b3 before the item was written – on KiCad the gate's stages S and F
  name KiCad's schematic and BOM, and `route all` says nothing was written to the KiCad PCB (test_kicad_fab).
  *(edakit-6a)* [2026-11-02]
- [x] TD-90 - **OK for #184:** given; merged as edakit 0.4.16 (#184, feac91e) – issues by others: `wrap.yml` wraps
  their texts, sealed and numbered, the owner answers with `review`, `accept` or `reject`; `wrap.yml` run by hand on
  #153 posted nothing, as it should on the owner's own issue. *(edakit-60)* [2026-11-01]
- [x] TD-80 - **E-17 and M-10 upstream:** posted on the owner's word – E-17 as easyeda-api-sdk #52, M-10 as
  easyeda-mcp-pro #818 with the fix #819 from the fork's `fix/rebuild-copper-batch-reconcile`, only a net's pours in
  one call – a refill left out on the owner's word (#172). *(edakit-ce)* [2026-11-01]
- [x] TD-35 - **D.9** The gallery: the index, the Christmas bell with its variants from release 20261101-142527,
      pytree in text (its pictures: TD-82), the examples as cards (#174). [2026-11-01]
- [x] TD-34 - **D.7** The cost line of the start page from the evals' baseline; a gate run's and a design's cost
      unmeasured yet, outreach.md's fact sheet left to its revision (#174). [2026-11-01]
- [x] TD-33 - **D.6** The reader pages: adding a rule, working on edakit, edakit as a meta-harness (#174). [2026-11-01]
- [x] TD-32 - **D.5** Every chapter condensed in place and reviewed, chapter 13 the history; the third fewer words not
      reached – the statements won, the owner decides on the rule (TD-81) (#174). [2026-11-01]
- [x] TD-31 - **D.4** The short tables linked to the catalog, the catalog split into 35 pages, 10.5 one entry per
      command with its generated synopsis (#174). [2026-11-01]
- [x] TD-30 - **D.3** The navigation as data by reader, the sources as "Inside edakit", footer and feedback lines
      (#174). [2026-11-01]
- [x] TD-29 - **D.2** The entry layer: the start page, the quickstart with its test, How it works, the buzzword rule
      (#174). [2026-11-01]
- [x] TD-79 - **merge.py and generated files:** a conflict only in generated output – the catalog page, the handbook's
  generated sections – is resolved and regenerated, a conflict in anybody's text still stops the merge; with it the
  check version reads the merge base, so a branch behind main is no longer taken for wrongly numbered (#168).
  [2026-11-01]
- [x] TD-50 - **V.7** `edakit = ">=0.4"` under `[project]` in edakit.toml: STRUCT.edakit notes an edakit that does not
  meet it, the working agreements' first line names the edakit that runs, the session hook warns on a mismatch (#169,
  edakit 0.4.13). [2026-11-01]
- [x] TD-48 - **V.5** Branches left lying around: eight fully merged ones deleted on origin on the owner's word
  (features/proposals, rules/proposals, six notes/*); the `claude/*` and `ccr-*` ones were gone already; the rest
  belongs to open pull requests of other sessions. [2026-11-01]
- [x] TD-69 - **Where CI.0 runs:** which machine with the harnesses, a GPU for the self-hosted models, a Copilot
      plan and a Mistral key – dropped: comes back with CI.0; a concept's steps come into this list only once it is
      being built. [2026-11-01]
- [x] TD-68 - **CI.7** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-67 - **CI.6** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-66 - **CI.5** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-65 - **CI.4** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-64 - **CI.3** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-63 - **CI.2** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-62 - **CI.1** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-61 - **CI.0** dropped: comes back when claude-independence.md is built, its table keeps the step. [2026-11-01]
- [x] TD-59 - **OK for #129, #130, #131:** given; #129 and #130 went as #135 and #136 (a generated handbook section
      fixed at its source), #131 as 0.4.2. [2026-11-01]
- [x] TD-40 - **E-10, E-11 and E-13 taken up:** NO_POURS regions instead of the notch, the tooling holes stay while
      the pours fill, pins modified in place, the orphan sweep kept – live on coin-cell-led; edakit 0.4.10 (#163).
      [2026-11-01]
- [x] TD-39 - **E-9, local projects through the API:** edakit 0.4.2 (#131). [2026-11-01]
- [x] TD-38 - **E-3 and E-7, the PCB tab and the DRC:** edakit 0.4.6 (#136); a full routing run without reload is the
      next project's. [2026-11-01]
- [x] TD-37 - **E-2, the one click goes:** the Channel ID into the schematic parts, old ones fixed by `route drc` –
      edakit 0.4.4 (#135). [2026-11-01]
- [x] TD-52 - **The switch to 1.6.0:** edakit 0.4.0 (#121), "Tested with" in 0.4.2; on the way E-17 (0.4.7, #151) and
      M-10 (0.4.9, #157) found and taken care of; pytree and the bell take the plugin with their next updates. [2026-11-01]
- [x] TD-78 - **K.9** "Released with edakit X.Y.Z" as the last line of the notes of `edakit release publish`, linked to
      that version; `[release] publish.credit = false` leaves it out – merged as edakit 0.4.8 (#154, 08a6951).
      [2026-11-01]
- [x] TD-72 - **K.3** The issue forms – bug, question, "built with edakit" with the label `gallery` – and "Questions
      and bugs" in the README; merged as edakit 0.4.8 (#154, 08a6951). [2026-11-01]
- [x] TD-71 - **K.2** The README's "What it runs, sends, fetches" and the texts of decision 5 in `plugin.json` and
      `marketplace.json`, `plugin.json` without a version; merged as edakit 0.4.8 (#154, 08a6951) – the plugin's text
      of TD-34 settled. [2026-11-01]
- [x] TD-47 - **V.4** main protected: the rulesets main and tags and the merge settings as files in `.github/rulesets/`
  (#119), applied with `.github/rulesets.py apply` on the owner's word once everything in flight had landed; the marker
  tag `protected-2026-11-01` on 71f807f; the skills write a fragment per change (#120); main-updates dropped an hour
  later on the owner's word – its bypass needs `--admin` on every merge, which auto mode refuses (#156). [2026-11-01]
- [x] TD-77 - **K.7** dropped: the launch is not in implementation – the step stays in outreach.md's table until it
      is (the owner: a concept's steps come here only once they are built). [2026-11-01]
- [x] TD-76 - **K.6** dropped the same way: the launch week stays in outreach.md. [2026-11-01]
- [x] TD-75 - **K.5, the bell in hand** dropped the same way: the photo and video stay in outreach.md (decision 1).
      [2026-11-01]
- [x] TD-74 - **K.5** dropped the same way: the kit stays in outreach.md. [2026-11-01]
- [x] TD-73 - **K.4** dropped the same way: the directory submission stays in outreach.md; it comes back here once
      K.2 is merged and the owner starts it. [2026-11-01]
- [x] TD-70 - **The social preview uploaded:** by the owner from `docs/concepts/new/outreach/social-preview.png` –
      GitHub reports `usesCustomOpenGraphImage` true; K.1 of outreach.md complete (no commit, a setting). [2026-11-01]

- [x] TD-60 - **OK for #138:** given; the rule proposal #103 (GEO.pour, bare area per side) merged as edakit
      0.4.3 (3cc88ba), #103 closed. [2026-11-01]
- [x] TD-44 - **The Claude GitHub app uninstalled:** dropped on the owner's word – the app is Claude Code on the web's
      access to the repositories; the proposals Action no longer fetches its token (0.3.1), and main's ruleset (TD-47)
      keeps it off main. [2026-11-01]
- [x] TD-58 - **OK for #121, easyeda-mcp-pro 1.6.0:** given, merged as edakit 0.4.0 (5ae332d). [2026-11-01]
- [x] TD-54 - **M-6, the BOM's duplicates:** on 1.6.0 each part listed once; the removal went, SYNC.bom reports a
      designator listed twice – edakit 0.4.0 (#121). [2026-11-01]
- [x] TD-53 - **M-6, all pages at once:** dropped – `all_pages` answers with the parts of every open schematic, the
      template's included, without their page; edakit stays page by page, recorded in upstream/README.md – edakit 0.4.0
      (#121). [2026-11-01]
- [x] TD-43 - **P.6, the live test of the proposals pipeline:** the setting for pull requests on; three sealed test
      proposals – #108 broken seal: the workflow's question, no Claude run; #109 covered: rejected as LIM.range and
      closed; #110 asks to change triage-rule: rejected at "Safe?", no commit –; a batch of six real ones (#112–#117)
      triaged once each, #112, #114, #115 and #116 built into #122 by the workflow's token. Found and fixed: a
      left-over commit (#103's 9aad156) conflicting only in the catalog page (#111, 0.3.2); a result written before
      its commit and a placeholder left in the pull request (#125). [2026-11-01]
- [x] TD-42 - **P.1 to P.5, the proposals pipeline:** Claude reads with the workflow's own token, a fixed job checks
      the commit against PIPELINE before the push, the queue triages once and takes adopted issues of others (#105,
      edakit 0.3.1). [2026-11-01]
- [x] TD-51 - **The bridge extension 1.6.0 in EasyEDA:** imported by the owner; `edakit doctor` and the self-test:
      extension 1.6.0 = server 1.6.0. [2026-11-01]
- [x] TD-46 - **V.3** The notes lane: `.github/notes.py` lands a session's edits of concepts and TODO.md on the newest
  main without an OK – the diff, three-way, from any worktree; a pull request from notes/<topic>, merged by the script
  once green, no GitHub auto-merge; `paths` holds notes/* to the lane; this tick its first run (#107, 897ae0d).
  [2026-11-01]
- [x] TD-56 - **4.5** A project without a requirements file does not release: DOCS.file, open like a required
  sign-off – `edakit check` passes, `--release` and the gate do not; built before the bell's D-39 on the owner's word,
  the bell has its file (#106, edakit 0.3.0). [2026-11-01]
- [x] TD-45 - **V.1 and V.2** edakit 0.2.0, the first version: the number in `edakit/__init__.py`, `edakit --version`
  and the manifest's `tools.edakit`, the changelog from 2026-11-01 on, the fragments in `changes/`, `.github/merge.py`
  (merges while main keeps its number – not strict), the checks `paths` and `version`, `release.yml` (tag v0.2.0 and the
  GitHub release set); CLAUDE.md "A merge is a version", README, handbook 2.3, 10.5, 14.4, the glossary (#104, 1cb2d68).
  [2026-11-01]
- [x] TD-25 - **easyeda-mcp-pro 1.6.0 prepared:** branch `mcp-160`, the pin raised, both patches applied, the patched
  extension built to `~/.easyeda-mcp-pro/easyeda-bridge-extension-1.6.0.eext`; on the way 1.6.0's one break for
  edakit – the PCB lists refuse projectId "current" – met in `list_pcb_components` (branch `mcp-160`, not merged).
  *(edakit-e4)* [2026-11-01]
- [x] TD-55 - **4.4** The tree moved to edakit before its order instead (its EK-5 lifted EK-1), in pytree: D-50 to
  D-54, merged on its main with pytree#34 – `hardware/boards/tree.toml` written by its script `baumplan`, its scripts
  under `[scripts]` (`review_paket.py` only reads the release), `elektrotechniker` and `pcb-pruefer` deleted rather
  than kept with `replaces` – edakit's reviewers signed M-1, M-5 and M-6 –, `hardware/requirements.toml` accepted.
  [2026-11-01]
- [x] TD-28 - **When a release brings M-2 to M-4:** merged into TD-26 – the second half of following the same pull
  requests; TD-25 split into TD-25 and TD-51 to TD-54 at the same time. *(edakit-e4)* [2026-11-01]
- [x] TD-41 - **M-9 (was E-15):** reproduced live on 3.2.209 with the bridge of 1.4.0 (code unchanged on 1.6.0) – not
  "Invalid device": the bridge drops `mirror`, `addIntoBom` and `addIntoPcb` of a placed part and reports `applied`;
  posted as #804 with the pull request #805 from the fork's `fix/place-component-flags`; edakit's `place` takes every
  part with `bom: false` out of the BOM afterwards, not only those with an LCSC number (cb9ddc7). *(edakit-e4)*
  [2026-11-01]
- [x] TD-27 - **On the owner's word – post:** E-1 to E-16 checked live on EasyEDA Pro 3.2.209 and against the JSDoc of
  its types, then posted: #45 to #51 at easyeda/easyeda-api-sdk and comments to #36 and #38; E-3 watched, E-2's Channel
  ID, E-7 to E-10 and E-13 ours, documented or met, E-14 by design, E-15 moved to M-9 (5d2ee55). *(edakit-e4)*
  [2026-11-01]
- [x] TD-2 - **Read the circuit-language sketch in peace:** read by the owner; the sketch itself was closed on
  2026-10-31 (bd227e3) and lives on in circuit-language-plan.md and circuit-dsl.md (6df3b09). *(edakit-29)* [2026-11-01]
- [x] TD-1 - **Update the edakit plugin:** the owner updated it to 8c6652c and reloaded (aec84ee).
  *(edakit-be, automatic-christmas-bell-b3)* [2026-11-01]
- [x] TD-24 - **The check candidates of the review at the order (5.5):** decided and built – FILES.order/lead,
  PARTS.fact/rohs, the makers' RoHS and REACH statements (2f659d6). [2026-11-01]
- [x] TD-23 - **5.11, the makers' interfaces:** dropped – future work, nobody asks the makers (the owner's
  decision); handbook 8.4 names them (545ee3a). [2026-11-01]
- [x] TD-22 - **Step 0 (5.0), the makers' forms:** the four profiles recorded, JLCPCB's order number gone, PCBWay's
  upload after "Save to Cart", Eurocircuits' "Add to basket", AISLER without a cart; branch makers-step0 merged
  (dcc0dfb, ce3e897). [2026-11-01]
- [x] TD-21 - **Step 0b (5.0), EasyEDA's ODB++ on a probe board:** component layers with package, pins and MPN,
  turned as F-7 assumes; SYNC.odb's RoundRect mask openings fixed (6062591, ce3e897). [2026-11-01]
- [x] TD-20 - **5.7, 5.12:** the skill cart live at JLCPCB and PCBWay, into the cart, nothing ordered (ce3e897).
  [2026-11-01]
- [x] TD-19 - **5.8:** the skill cart live at Eurocircuits, into the basket, nothing ordered (ce3e897). [2026-11-01]
- [x] TD-18 - **5.10:** AISLER live, stopped before "Continue to Checkout", nothing ordered (ce3e897). [2026-11-01]
- [x] TD-17 - **CPL rotations per maker:** `[cpl] zero` and `[cpl.turns]` in the makers' profiles (ce3e897).
  [2026-11-01]
- [x] TD-16 - **JLCPCB's customs "Product Description":** the key `customs` of `[order]` (ce3e897). [2026-11-01]
- [x] TD-15 - **The ODB++ export upstream (M-4):** branch feat/odb-export built in the fork (2395015), issue and
  pull request posted as #798/#799 with M-1 to M-3; following them is the open item above. [2026-11-01]
- [x] TD-14 - **The example coin-cell-led at its next `edakit gate --easyeda`:** routed and released again, A4, A5,
  B1, B3, B7 and C4 hold, M-5 signed for the new fab hash (e3e1290). [2026-11-01]
- [x] TD-13 - **LT-9, the led-bar example on real footprints:** the placement plan fits its LCSC footprints, the
  Pico 2's pins in `symbol_differs` (dc07193). [2026-11-01]
- [x] TD-12 - **The KiCad live test with the owner:** all seven steps, LT-1 to LT-11 in the concept (4dbf4fc).
  [2026-11-01]
- [x] TD-11 - **The bell's L.9 and its T-Display on the data path:** done in the bell's session, its branch
  edakit-current (2dd5f55). [2026-11-01]
- [x] TD-10 - **The notices after the merge into main:** the bell and pytree-27 told of F-6's placeholder warning
  and the walkthrough gaps' changes to their gate; the plugin follows main at 868e942 (59b62db). [2026-10-31]
- [x] TD-9 - **Live runs of design as text:** 2.2 (`[routing] drc_rules` "write"), 3.6 (the way back into the
  PCB), M-6 not voided by a footprint, and what was found on the way – built (bc44fa7). [2026-10-31]
- [x] TD-8 - **The owner's look at the footprint in EasyEDA:** looked at, the throwaway projects edakit-probe-*
  deleted (14e98bc). [2026-10-31]
- [x] TD-7 - **B2, the hole unit of `PCB_PrimitivePad.create`:** read back in live run 3.6 (59e0939). [2026-10-31]
- [x] TD-6 - **W.2 to W.5, the wired schematic:** merged into main, the concept done (81cd5f2, 2d475fc, d379775,
  868e942). [2026-10-31]
- [x] TD-5 - **D.1, the style guide and the glossary:** with test_style.py and test_references.py (2b37669).
  [2026-10-31]
- [x] TD-4 - **Walkthrough 2, the 555 blinker on KiCad:** the run up to RELEASED (123389b); boards not ordered –
  the owner's decision at the release (7999d5a). [2026-10-31]
- [x] TD-3 - **ODB++ on the KiCad tool chain:** `kicad-cli` exports it for a maker that takes it (82039a8). [2026-10-31]
