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
- [ ] **ODB++ on the KiCad tool chain:** edakit exports ODB++ only through EasyEDA (`easyeda_export_odb`); a project
      with `toolchain = "kicad"` and AISLER among its makers gets F-7's "not exported" – `kicad-cli pcb export odb`
      would give it from KiCad's own board (found when ordering met the KiCad tool chain on main).

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
