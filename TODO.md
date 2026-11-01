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
- [x] **Step 0b (5.0)** (2026-11-01, a probe board in EasyEDA, branch `makers-step0b`): EasyEDA's ODB++ – through
      `easyeda_export_odb` and by hand – has component layers with package, pins and the MPN as device name, turns
      clockwise as F-7 assumes, and keeps a part with `bom: false` in it without a mark (the skill marks it). SYNC.odb
      drew EasyEDA's RoundRect mask openings as obrounds – fixed for SYNC.odb, the fab hash unchanged; both exports pass
      it now. Record `tests/fixtures/makers/aisler/step0b_2026-11-01.md`.
- [x] **JLCPCB's customs "Product Description" as a key of `[order]`** (the owner's decision of 2026-11-01), built
      on 2026-11-01: `customs = { category, hs_code }`, outside order.json and the fab hash; JLCPCB's profile lists
      the 62 entries with an HS code, FILES.order fails one it does not offer and names a missing key as information;
      the skill cart sets it, or asks the owner without it (handbook 10.2).
- [x] **5.7, 5.12:** the skill cart live at JLCPCB and PCBWay (2026-11-01, the 555 blinker, a copy of the example):
      every check passed, into the cart, order record written, nothing ordered.
- [ ] **5.8:** Eurocircuits live – stopped, as it must, at "Board thickness": 1.6 mm is not among Eurocircuits'
      thicknesses (1.55 is its standard). Again with a board of a thickness it makes, or the owner's word on 1.55.
- [ ] **5.10:** AISLER live – ran on 2026-11-01 and stopped, as it must, at ORDER.parts: R1 and R2 (UNI-ROYAL
      0805W8F7503T5E, 0805W8F2000T5E) are out of stock at AISLER. On the way built: SYNC.odb's edge tolerance, the MPN
      in every KiCad footprint (AISLER assigns by it, not by LCSC numbers), the profile's fields on AISLER's /checkout
      (the owner's word: opened by its address, stop before "Continue to Checkout") – ORDER.form passed. Left: a run
      with parts AISLER has, up to the price on /checkout (`tests/fixtures/makers/aisler/live_2026-11-01/`).

### Needs the makers

- [ ] **5.11:** ask JLCPCB (API access, an assembly interface for partners), PCBWay (partner API), AISLER (upload key,
      ODB++ from EasyEDA for assembly) and Beta LAYOUT (API); build what is granted.

### Needs the owner's word

- [ ] The check candidates of the review at the order (implementation plan, 5.5): lead graded by purpose already at
      the release (F-6); a line of the page text that addresses the assistant as a finding of `edakit cart check`; a
      BOM part without `compliance.rohs` on a board for sale; the maker's RoHS and REACH statements in its profile.
      Each becomes a rule only with the skill add-rule, on the owner's word.

## What edakit needs from EasyEDA Pro and easyeda-mcp-pro ([upstream/README.md](upstream/README.md))

The requirements E-1 to E-16 on EasyEDA Pro and M-1 to M-8 on easyeda-mcp-pro, gathered on 2026-11-01 under the
owner's rules there: no click because of the API, no self-extended MCP server, the latest state checked first.

- [ ] **On the owner's computer – the newest versions live:** EasyEDA Pro 3.2.209 (3.2.206 is installed) and
      easyeda-mcp-pro 1.6.0 (the pin is 1.4.0) with the patched extension of the same version; E-1 to E-4 and E-7
      checked again, the self-test, one gate run of the example; M-6: `scope: "all_pages"` of
      `easyeda_schematic_components` instead of focusing page after page, and the BOM's duplicates. Then the pin raised
      in `mcp-server.sh`.
- [ ] **M-1 to M-4 upstream, posted on 2026-11-01** (#792/#793, #794/#795, #796/#797, #798/#799): review comments
      answered on the fork's branches, rebased when `main` moves; the comment "I agree to the Contributor Permission v1
      in CONTRIBUTOR-LICENSING.md", when the maintainer asks for it, from the owner.
- [ ] **M-5 and M-7 upstream, posted on 2026-11-01** (#800, #801): follow them; M-6 not posted – #539 has met it as far
      as EasyEDA's API lets it (upstream/README.md).
- [ ] **On the owner's word – post:** E-1 to E-16 at easyeda/easyeda-api-sdk after the live check above – to #33, #34, #36, #38 and #39 as comments. Before
      each the check of "The latest state".
- [ ] **When a release brings M-2 to M-4:** pin raised, the original extension, `bridge-extension-patch.sh` and
      `odb-tool-patch.mjs` removed, handbook 2.4, 2.5 and 9.1 follow.

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
