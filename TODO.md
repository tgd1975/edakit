# TODO

Open work that needs the owner's computer, a maker or the owner's word. The state of every step is in
[docs/concepts/new/implementation-plan.md](docs/concepts/new/implementation-plan.md) and in the concepts the sections
name; this list is what is left to do of them, in the order it can be done. Tick an item off with the commit that
does it.

**Taking an item.** Several sessions work on edakit at once. Before a session starts an item, it lists the others
(`ListAgents`, `git worktree list`), asks each running edakit session which item it holds, and takes one that nobody
holds and whose files no open branch touches – the concepts' tables name each step's files. An item that waits for
another (W.4 after W.2) is agreed with the session holding that one and merged after it. Each item gets a worktree of
its own beside the main clone, named for it (`../edakit-w4`, branch `wired-w4`), so `git worktree list` shows who
holds what; the main clone belongs to whoever has it checked out, and its uncommitted changes are not anyone else's
to touch.

## Ordering at the manufacturer (phase 5, [ordering.md](docs/concepts/done/ordering.md))

Built offline and tested on recorded data on 2026-10-30, merged into main the same day: the order form as keys, the
makers' profiles (JLCPCB, PCBWay, Eurocircuits, AISLER), the checks per maker, `edakit cart fields|prepare|check|
actual` with B-1 to B-7, the order record, the skill cart, the review at the order, ODB++ with F-7. Nothing of it has
run against a maker's page or EasyEDA yet.

### Needs the owner's computer – a session attached to it, Claude in Chrome, the makers' accounts

- [ ] **Step 0 (5.0) and the live runs – the merge of branch `makers-step0`, on the owner's OK:** the four profiles
      recorded from the forms (2026-10-31), JLCPCB's order number gone (`former_placeholder`, `mark = "specify"`
      refused; the bell needs `mark = "remove"` or a barcode before its next order), the skill cart stopping at every
      consent in the owner's name, and what the live runs found fixed in `edakit cart` (numbers, uploads a page does
      not show or takes after the cart, matching in the maker's review, checkout fields, a cart line named by size).
      Evidence in `tests/fixtures/makers/` (LIVE.md); full suite green. B6 (Economic on a round board with two customer
      tooling holes) not checked.
- [x] **PCBWay:** the files go up after "Save to Cart" (Gerber, BOM, centroid in Altium's mil format, assembly
      drawings; "Submit the File Now" starts the review); the assembly price shows online but without components until
      the review; one `bom_<b>_mpn.csv` serves PCBWay and Eurocircuits – both took it.
- [x] **Eurocircuits, AISLER, the cart:** Eurocircuits "Add to basket" on its Summary page; AISLER has no cart – the
      skill stops before "Continue to Checkout".
- [ ] **Step 0b (5.0), under the EasyEDA claim, on a throwaway board:** build and import the bridge extension with
      ODB++ (`bash edakit/easyeda/bridge-extension-patch.sh`; `mcp-server.sh` patches the server itself), export with
      `easyeda_export_odb` and by hand (File > Export > ODB++) and compare: component layers with packages, pins and
      part numbers; the parts kept out of EasyEDA's BOM left out or not; the rotation sense (F-7 assumes ODB++'s
      clockwise). No component layers: KiCad as the converter for AISLER, or no AISLER. Seen on 2026-10-31: AISLER
      takes kicad-cli's ODB++ of led-bar with every part, offers edakit's properties as BOM columns ("edakit", "lcsc",
      MPN), leaves the tooling holes out; D1 (SS34) needed a part by hand, the LEDs were matched by value only.
- [ ] **JLCPCB's customs "Product Description" as a key of `[order]`** (the owner's decision of 2026-11-01): a key –
      the category with its HS code, outside the fab hash – that the skill cart sets and FILES.order names when it is
      missing at a maker that asks for it (JLCPCB's Quote & Order, a cascader of category and HS code; the list in
      `tests/fixtures/makers/jlcpcb/step0_2026-10-31.md`). Built with the skill add-feature.
- [x] **5.7, 5.12:** the skill cart live at JLCPCB and PCBWay (2026-11-01, the 555 blinker, a copy of the example):
      every check passed, into the cart, order record written, nothing ordered.
- [ ] **5.8:** Eurocircuits live – stopped, as it must, at "Board thickness": 1.6 mm is not among Eurocircuits'
      thicknesses (1.55 is its standard). Again with a board of a thickness it makes, or the owner's word on 1.55.
- [ ] **5.10:** AISLER live – the release's SYNC.odb warns: kicad-cli's ODB++ of the blinker differs from its Gerber
      files on the bottom silkscreen (1.06 mm² at 27.27, 1.57) and the top copper (0.05 mm² at 40.96, 17.53); find why,
      then the run.

### Needs the makers

- [ ] **5.11:** ask JLCPCB (API access, an assembly interface for partners), PCBWay (partner API), AISLER (upload key,
      ODB++ from EasyEDA for assembly) and Beta LAYOUT (API); build what is granted.

### Needs the owner's word

- [ ] Post the upstream issue and pull request for the ODB++ export ([issue](upstream/issue-5-odb-export.md),
      [pull request](upstream/pr-4-odb-export.md)); the branch of the fork is not built yet.
- [ ] The check candidates of the review at the order (implementation plan, 5.5): lead graded by purpose already at
      the release (F-6); a line of the page text that addresses the assistant as a finding of `edakit cart check`; a
      BOM part without `compliance.rohs` on a board for sale; the maker's RoHS and REACH statements in its profile.
      Each becomes a rule only with the skill add-rule, on the owner's word.

## Live runs of design as text (2.1–2.4, 3.6 of the [implementation plan](docs/concepts/new/implementation-plan.md))

Ran on 2026-10-31 in throwaway projects, the footprint checked by the owner in EasyEDA, the throwaway projects and
the probe's Custom Config removed; the results are under each live run of the plan. The bell's T-Display on the data
path is done in the bell (2026-11-01, on its main, its D-30).

Built on 2026-10-31 from them: `[routing] drc_rules = "write"`; M-6 on the electrical hash; the way back into the PCB
after `part build`; the waits after `openProject`, `symbol_differs` in `schematic create`, the panel guard of
`rename_schematic`, projects found in EasyEDA's folder. led-bar's `[place]` stays as it is: its LED row and U1 are the
data of tests (`test_pcb`), not a board to order.

## Walkthrough gaps ([walkthrough-gaps.md](docs/concepts/done/walkthrough-gaps.md))

Built and decided on 2026-10-31; what is left runs live.

- [ ] **The example at its next `edakit gate --easyeda`:** a new fab hash – C4 puts `mark = "remove"` into order.json
      of a `[looks]` board –, so M-5 once more; on the way look at A4 (`route all` on the round board without
      Freerouting's "geometry is degenerate"), B1 (protocol L: the vias' ring 0.15 mm, not 1.000), A5 (BT1's "+" on
      the polarity sheet), B3 (GEO.silk grade body on BT1's cell) and B7 (the BOM from the board's schematic with the
      other tabs closed).

## The graph as TOML ([circuit-language-plan.md](docs/concepts/done/circuit-language-plan.md))

L.1 to L.8 built on 2026-10-31.

L.9 done in the bell on 2026-11-01 (on its main, edakit bc44fa7): the five boards converted, the
sign-offs rehashed, the mentions of `graph.json` renamed, all five RELEASED.

## KiCad tool chain ([kicad-toolchain.md](docs/concepts/done/kicad-toolchain.md))

Built and merged into main on 2026-10-30, tested offline and in CI against KiCad 10 on the led-bar example. The live
test with the owner ran on 2026-10-31, all seven steps; what it found and what was built from it (LT-1 to LT-11, branch
`kicad-live-fixes`) is in the concept's section "Live test".

- [ ] **LT-9, the led-bar example on real footprints:** its fixed rows in `[place]` do not fit the LCSC footprints (the
      LEDs 4 mm apart at 4.2 mm, U1 in the keep-out of the hole at (3.5, 3.5), J1 4.3 mm off the edge), and its
      Pico's entry names pins 41 and 43 SWCLK and SWDIO where the library's symbol has them the other way round, its
      GP pins by their short names. The example is the tests' fixture on test footprints (test_pcb's `led_bar_geo`),
      so the rows move only with the tests that read them; the pin names want the datasheet first.

## The documentation for its readers ([documentation.md](docs/concepts/new/documentation.md))

Decided on 2026-10-31; D.1 (the style guide, the glossary and their tests) built the same day. D.2 to D.7 not before
the other todos in this list are done: the documentation describes what they leave behind.

Each step starts on the owner's word, one per branch, under the concept's rules for what the automation reads –
sources, data and code untouched; a text that is generated or used elsewhere stays; unsure, ask:

- [ ] **D.2** The entry layer: the README as the start page of one screen, `docs/quickstart.md` with its test,
      `docs/how-it-works.md` with the pipeline drawing and a transcript; `test_plugin.py` pointed at the page that
      lists skills and agents.
- [ ] **D.3** The site: the navigation as data, by reader and by station (The circuit, The board), short titles;
      `organisation.md` and the brand page on it; "Inside edakit" with its index and the source line; the footer and
      feedback lines; prototypes off the navigation.
- [ ] **D.4** The reference: 10.5 as entries with the generated synopsis; the catalog page split; the chapters'
      generated lists as the short kind.
- [ ] **D.5** The chapters in place, condensed to a third fewer words with no statement lost, worst first – 8, 3, 5, 7,
      4, 10, then the rest –, the review for meaning after each; chapter 13 takes the history.
- [ ] **D.6** The reader pages "Adding a rule" and "Working on edakit".
- [ ] **D.7** The "is it for me" numbers from the evals; the findings on sources (the plugin's descriptions say "JSON
      hardware graph") to the owner.
