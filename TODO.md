# TODO

Open work that needs the owner's computer, a maker or the owner's word. The state of every step is in
[docs/concepts/new/implementation-plan.md](docs/concepts/new/implementation-plan.md) and in the concepts the sections
name; this list is what is left to do of them, in the order it can be done. Tick an item off with the commit that
does it.

## Ordering at the manufacturer (phase 5, [ordering.md](docs/concepts/done/ordering.md))

Built offline and tested on recorded data on 2026-10-30, merged into main the same day: the order form as keys, the
makers' profiles (JLCPCB, PCBWay, Eurocircuits, AISLER), the checks per maker, `edakit cart fields|prepare|check|
actual` with B-1 to B-7, the order record, the skill cart, the review at the order, ODB++ with F-7. Nothing of it has
run against a maker's page or EasyEDA yet.

### Needs the owner's computer – a session attached to it, Claude in Chrome, the makers' accounts

- [ ] **Step 0 (5.0), per maker – JLCPCB, PCBWay, Eurocircuits, AISLER –, nothing ordered:** can Claude in Chrome put
      a local file into the upload fields; do the fields read back as text; can it save screenshots to a file; can the
      placement preview be opened again from the cart (M-2)? Record each form in its profile – labels, words, values,
      `ignore`, CPL format, cart button – and set `recorded` to the date. Keep the page texts of one quote and one past
      order as test data; read the terms on automated use, for the record.
- [ ] **JLCPCB's order number:** gone since May 2026, as its help article of 2026-05-22 reports? Then the placeholder
      and `mark = "specify"` leave `edakit/makers/jlcpcb.toml`; otherwise `rules.placeholder_gone` goes. The form's
      words for `barcode` and `serial_number`. With it, whether Economic PCBA takes a round board on two customer
      tooling holes without rails (walkthrough-gaps B6).
- [ ] **PCBWay:** its BOM template – one `bom_<b>_mpn.csv` for PCBWay and Eurocircuits, or one file per maker; when the
      assembly price comes (BOM quotation by hand); whether the files go up after "Save to Cart".
- [ ] **Eurocircuits, AISLER:** the cart or basket button – none is recorded, so the skill stops before the cart.
- [ ] **Step 0b (5.0), under the EasyEDA claim, on a throwaway board:** build and import the bridge extension with
      ODB++ (`bash edakit/easyeda/bridge-extension-patch.sh`; `mcp-server.sh` patches the server itself), export with
      `easyeda_export_odb` and by hand (File > Export > ODB++) and compare: component layers with packages, pins and
      part numbers; the parts kept out of EasyEDA's BOM left out or not; the rotation sense (F-7 assumes ODB++'s
      clockwise). No component layers: decide KiCad 9 as the converter for AISLER, or no AISLER.
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

### After the merge into main

- [ ] Tell the bell's session and pytree-27: F-6 now warns about JLCPCB's placeholder `JLCJLCJLCJLC` on a board – a
      new warning in their gate, to accept or to remove with the placeholder (`mark = "remove"`, a `barcode`).
- [ ] The shared tree follows main; the plugin follows (skills, agents and code changed).

## Walkthrough gaps ([walkthrough-gaps.md](docs/concepts/done/walkthrough-gaps.md))

Built and decided on 2026-10-31; what is left runs live.

- [ ] **B2, with step 3.6 under the EasyEDA claim:** build a footprint with a 1.0 mm hole, read it back three ways
      (state `Hole`, `getAllPinsByPrimitiveId`, Gerber drill) – does `PCB_PrimitivePad.create` take holes in mil, as
      `pad_args` writes them, or in 10 mil?
- [ ] **The example at its next `edakit gate --easyeda`:** a new fab hash – C4 puts `mark = "remove"` into order.json
      of a `[looks]` board –, so M-5 once more; on the way look at A4 (`route all` on the round board without
      Freerouting's "geometry is degenerate"), B1 (protocol L: the vias' ring 0.15 mm, not 1.000), A5 (BT1's "+" on
      the polarity sheet), B3 (GEO.silk grade body on BT1's cell) and B7 (the BOM from the board's schematic with the
      other tabs closed).
- [ ] **Tell the bell's session and pytree-27 after the merge into main:** findings name pins by name or role
      ("U2.VDD (16)" for "U2.16 (VDD)") – a sign-off pattern on the old text stops matching; C4 changes the fab hash of
      a board with `[looks]` and `[order]` and no `mark`; FILES.order warns about `[tooling]` on an Economic board that
      nothing tells the maker about; LIM.p rows for LEDs change the simulation's counts; an accepted simulation
      finding counts as waived in the gate, an unaccepted simulation warning as a warning – it wants an accept in the
      sign-off file where it failed before.

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

- [ ] **The live test with the owner** (the concept's section "Live test", steps 1 to 7): KiCad 10 from the PPA,
      the example as a KiCad project, PCB, routing, gate, the placer T.1 on both tool chains, a scratch copy of the
      bell's main board; with it the recorded KiCad export of T.6 and the probe of T.7.

## Walkthrough 2: a 555 blinker on KiCad ([walkthrough-kicad-555.md](docs/concepts/new/walkthrough-kicad-555.md))

Decided on 2026-10-31; nothing to build in edakit beforehand. Simulation over time is out of scope.

- [ ] **The run**, where KiCad 10, ngspice and Freerouting are installed: `examples/blinker-555` (2×AAA on the
      bottom, slide switch, CMOS 555, red LED; JLCPCB Economic for the SMD parts, holder and switch by hand), steps 1
      to 12 up to RELEASED and `edakit export`; what breaks (E2 to E6) fixed on the way; handbook chapter 18,
      `tests/test_walkthrough_kicad.py`. Afterwards: the KiCad live test's steps 1, 3, 4 and 5 count as done, and
      whether boards are ordered is decided.

## The schematic with every connection drawn through ([wired-schematic.md](docs/concepts/new/wired-schematic.md))

Decided on 2026-10-31; W.1 (the frame of the SVG optional) built and merged the same day. The rest starts on the
owner's word, one step per branch:

- [ ] **W.2** the wired style of `schematic draw`: `style` in the schematic file (labels without it), leads, rails,
      router, colours, the geometry check telling a crossing from a T, hand-wired boards drawn.
- [ ] **W.3** placement for wires: the module in the middle, channels as wide as the wires that must pass; the
      prototype's table as the test.
- [ ] **W.4** new-project asks for the style and writes the key; project-surveyor reports it.
- [ ] **W.5** `print` per pin in the parts entry, drawn beside the symbol's name; the Nano's and the Pico's entries.

## The documentation for its readers ([documentation.md](docs/concepts/new/documentation.md))

Decided on 2026-10-31; nothing built. Each step starts on the owner's word, one per branch, under the concept's rules
for what the automation reads – sources, data and code untouched; a text that is generated or used elsewhere stays;
unsure, ask:

- [ ] **D.1** `docs/style.md` and `docs/glossary.md`; `docs/organisation.md` points at the style guide;
      `tests/test_style.py` for the countable rules and `tests/test_references.py` for the 415 references and paths.
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
