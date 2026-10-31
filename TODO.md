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

- [ ] **Step 0 (5.0), the profiles:** the four makers' pages were read on 2026-10-31 with Claude in Chrome in the
      owner's accounts, nothing ordered – upload of a local file, read back, screenshots to a file work everywhere; the
      placement preview opens again from the cart at JLCPCB ("Product Details → Part Placement") and Eurocircuits
      ("Assembly Visualizer → CPL Editor"), PCBWay shows none (its engineers review the files); no maker's terms say
      anything on automated use. Notes and JLCPCB's quote text in `tests/fixtures/makers/<maker>/` on branch
      `makers-step0` (pushed; worktree `../edakit-step0`, session edakit-c9). The profiles of PCBWay, Eurocircuits and
      AISLER are recorded there, with tests (a field's `more = true` for lists read only in part). Left: JLCPCB's
      profile with the order number (below; the test helper `ordered()` of 58 tests orders with the placeholder), the
      consents the skill must stop at (JLCPCB's pre-checked assembly terms, PCBWay's "Agree" on export control,
      Eurocircuits' Terms of Sales), the merge on the owner's OK; no past order exists in the new accounts, so no
      order page as test data.
- [ ] **JLCPCB's order number – gone:** "Mark on PCB" offers only "Remove Mark" (preselected) and "2D barcode (Serial
      Number)" with its own dialog (2D barcode Only | Number Only | both; QR | Data Matrix; 5/8/10 mm; position). Left:
      the placeholder and `mark = "specify"` leave `edakit/makers/jlcpcb.toml`, F-6 still names a `JLCJLCJLCJLC` left on
      a silkscreen (the bell), the barcode words. Not checked: Economic PCBA on a round board with two customer tooling
      holes and no rails (walkthrough-gaps B6).
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
- [ ] **5.7:** the skill cart live at JLCPCB, up to the cart.
- [ ] **5.8:** Eurocircuits live, up to the basket.
- [ ] **5.10:** AISLER live, up to the cart (after step 0b).
- [ ] **5.12:** PCBWay live, up to "Save to Cart".

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
the probe's Custom Config removed; the results are under each live run of the plan. Left from them:

- [ ] **The bell's T-Display on the data path** (the bell's repository, its session – the owner hands it the prompt):
      the dry run's footprint data without `"symbol"`, `tdisplay_device.py symbol` stays an easyeda script; the esp32
      variant's circuit and layout hashes change once (M-1 anew, M-6 stays on the electrical hash).

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

- [ ] **L.9, on the owner's word, in the bell's session and not during an order:** `edakit graph convert` in the main
      configuration and the three variants, the sign-offs carried over; the bell's mentions of `graph.json`
      (`hardware/README.md`, `docs/decisions.md`, a comment in the esp32 firmware) name the generated file; the four
      round trips of the sketch once more, `edakit graph json` against the former `graph.json`. Scripts that read
      `graph` show as outdated once after the conversion (`edakit run` or `edakit scripts stamp`), and the firmware
      contract wants `edakit firmware` again.

## KiCad tool chain ([kicad-toolchain.md](docs/concepts/done/kicad-toolchain.md))

Built and merged into main on 2026-10-30, tested offline and in CI against KiCad 10 on the led-bar example.

- [ ] **The live test with the owner** (the concept's section "Live test"): steps 1, 3, 4 and 5 ran on a real
      project, the 555 blinker of handbook 18 (`examples/blinker-555`, released 2026-10-31). Open: step 2 (the led-bar
      example as a KiCad project, its schematic looked at in KiCad), step 6 (the placer T.1 on both tool chains) and
      step 7 (a scratch copy of the bell's main board); with them the recorded KiCad export of T.6 and the probe of
      T.7.

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
