# TODO

Open work that needs the owner's computer, a maker or the owner's word. The state of every step is in
[docs/concepts/new/implementation-plan.md](docs/concepts/new/implementation-plan.md) and in the concepts the sections
name; this list is what is left to do of them, in the order it can be done. An item that is done is ticked with its
date and the commit that does it and moves to [Closed todos](#closed-todos) at the end, newest first – by whichever
session learns it; one that is dropped says so. No item is deleted. Every item, in every section, open or closed, is a
line with a checkbox and an ID `TD-<n>` unique in this file, counted up and never reused; who adds an item takes the
next free ID and counts it up here. Next free ID: TD-36.

**Taking an item.** Several sessions work on edakit at once. Before a session starts an item, it lists the others
(`ListAgents`, `git worktree list`), asks each running edakit session which item it holds, and takes one that nobody
holds and whose files no open branch touches – the concepts' tables name each step's files. An item that waits for
another (W.4 after W.2) is agreed with the session holding that one and merged after it. Each item gets a worktree of
its own beside the main clone, named for it (`../edakit-w4`, branch `wired-w4`), so `git worktree list` shows who
holds what; the main clone belongs to whoever has it checked out, and its uncommitted changes are not anyone else's
to touch.

## For the owner

What only the owner can do – an account, a payment, an OK, hardware in hand, a click in Claude Code –, one line each
(`- [ ] TD-<n> **What:** command or link – why. *(session)*`), ticked off at once with the date and moved to
[Closed todos](#closed-todos). The items further down that wait for the owner stay where their step is.

Nothing open.

## Ordering at the manufacturer (phase 5, [ordering.md](docs/concepts/done/ordering.md))

Built offline and tested on recorded data on 2026-10-30, merged into main the same day: the order form as keys, the
makers' profiles (JLCPCB, PCBWay, Eurocircuits, AISLER), the checks per maker, `edakit cart fields|prepare|check|
actual` with B-1 to B-7, the order record, the skill cart, the review at the order, ODB++ with F-7. Run live at the
four makers on 2026-10-31 and 2026-11-01, into the cart and nothing ordered ([LIVE.md](tests/fixtures/makers/LIVE.md)).

## What edakit needs from EasyEDA Pro and easyeda-mcp-pro ([upstream/README.md](upstream/README.md))

The requirements E-1 to E-16 on EasyEDA Pro and M-1 to M-8 on easyeda-mcp-pro, gathered on 2026-11-01 under the
owner's rules there: no click because of the API, no self-extended MCP server, the latest state checked first.

- [ ] TD-25 **On the owner's computer – the newest versions live:** EasyEDA Pro 3.2.209 (3.2.206 is installed) and
      easyeda-mcp-pro 1.6.0 (the pin is 1.4.0) with the patched extension of the same version; E-1 to E-4 and E-7
      checked again, the self-test, one gate run of the example; M-6: `scope: "all_pages"` of
      `easyeda_schematic_components` instead of focusing page after page, and the BOM's duplicates. Then the pin raised
      in `mcp-server.sh`.
- [ ] TD-26 **The six issues with their pull requests at easyeda-mcp-pro, posted on 2026-11-01** – #792/#793 (stale sweep),
      #794/#795 (schematic PDF), #796/#797 (return depth), #798/#799 (ODB++), #800/#802 (createProject), #801/#803
      (pick-and-place as CSV): follow them, answer review comments on the fork's branches, rebase when `main` moves;
      the comment "I agree to the Contributor Permission v1 in CONTRIBUTOR-LICENSING.md", when the maintainer asks for
      it, from the owner. M-6 not posted – #539 has met it as far as EasyEDA's API lets it (upstream/README.md).
- [ ] TD-27 **On the owner's word – post:** E-1 to E-16 at easyeda/easyeda-api-sdk after the live check above – to #33, #34, #36, #38 and #39 as comments. Before
      each the check of "The latest state".
- [ ] TD-28 **When a release brings M-2 to M-4:** pin raised, the original extension, `bridge-extension-patch.sh` and
      `odb-tool-patch.mjs` removed, handbook 2.4, 2.5 and 9.1 follow.

## The documentation for its readers ([documentation.md](docs/concepts/new/documentation.md))

Decided on 2026-10-31; D.1 (the style guide, the glossary and their tests) built the same day. D.2 to D.7 not before
the other todos in this list are done: the documentation describes what they leave behind.

Each step starts on the owner's word, one per branch, under the concept's rules for what the automation reads –
sources, data and code untouched; a text that is generated or used elsewhere stays; unsure, ask:

- [ ] TD-29 **D.2** The entry layer: the README as the start page of one screen with the case for edakit (what you bring, what
      edakit brings, the walkthrough's count), `docs/quickstart.md` with its test, `docs/how-it-works.md` with the
      pipeline drawing and a transcript; `test_plugin.py` pointed at the page that lists skills and agents.
- [ ] TD-30 **D.3** The site: the navigation as data, by reader and by station (The circuit, The board), short titles;
      `organisation.md` and the brand page on it; "Inside edakit" with its index and the source line; the footer and
      feedback lines; prototypes off the navigation.
- [ ] TD-31 **D.4** The reference: 10.5 as entries with the generated synopsis; the catalog page split; the chapters'
      generated lists as the short kind.
- [ ] TD-32 **D.5** The chapters in place, condensed to a third fewer words with no statement lost, worst first – 8, 3, 5, 7,
      4, 10, then the rest –, the review for meaning after each; chapter 13 takes the history.
- [ ] TD-33 **D.6** The reader pages "Adding a rule" and "Working on edakit".
- [ ] TD-34 **D.7** The "is it for me" numbers from the evals; the findings on sources (the plugin's descriptions say "JSON
      hardware graph") to the owner.
- [ ] TD-35 **D.9** `docs/projects.md`, the gallery: the example and the bell now; pytree's entry with the information and the
      pictures the owner picks (needs the owner – the repository stays private); the tiny jukebox, the pedal and the
      steering wheel each after its conversion to edakit (`/edakit:new-project` with the inventory, a project of its
      own), on the owner's word.

## Closed todos

Done or dropped, newest first, each with its date and the commit that closed it. What closed before 2026-11-01 is
taken from the history of this file; an item rewritten on its way is listed once, in its last form.

- [x] 2026-11-01 TD-2 **Read the circuit-language sketch in peace:** read by the owner; the sketch itself was closed on
  2026-10-31 (bd227e3) and lives on in circuit-language-plan.md and circuit-dsl.md (6df3b09). *(edakit-29)*
- [x] 2026-11-01 TD-1 **Update the edakit plugin:** the owner updated it to 8c6652c and reloaded (aec84ee).
  *(edakit-be, automatic-christmas-bell-b3)*
- [x] 2026-11-01 TD-24 **The check candidates of the review at the order (5.5):** decided and built – FILES.order/lead,
  PARTS.fact/rohs, the makers' RoHS and REACH statements (2f659d6).
- [x] 2026-11-01 TD-23 **5.11, the makers' interfaces:** dropped – future work, nobody asks the makers (the owner's
  decision); handbook 8.4 names them (545ee3a).
- [x] 2026-11-01 TD-22 **Step 0 (5.0), the makers' forms:** the four profiles recorded, JLCPCB's order number gone, PCBWay's
  upload after "Save to Cart", Eurocircuits' "Add to basket", AISLER without a cart; branch makers-step0 merged
  (dcc0dfb, ce3e897).
- [x] 2026-11-01 TD-21 **Step 0b (5.0), EasyEDA's ODB++ on a probe board:** component layers with package, pins and MPN,
  turned as F-7 assumes; SYNC.odb's RoundRect mask openings fixed (6062591, ce3e897).
- [x] 2026-11-01 TD-20 **5.7, 5.12:** the skill cart live at JLCPCB and PCBWay, into the cart, nothing ordered (ce3e897).
- [x] 2026-11-01 TD-19 **5.8:** the skill cart live at Eurocircuits, into the basket, nothing ordered (ce3e897).
- [x] 2026-11-01 TD-18 **5.10:** AISLER live, stopped before "Continue to Checkout", nothing ordered (ce3e897).
- [x] 2026-11-01 TD-17 **CPL rotations per maker:** `[cpl] zero` and `[cpl.turns]` in the makers' profiles (ce3e897).
- [x] 2026-11-01 TD-16 **JLCPCB's customs "Product Description":** the key `customs` of `[order]` (ce3e897).
- [x] 2026-11-01 TD-15 **The ODB++ export upstream (M-4):** branch feat/odb-export built in the fork (2395015), issue and
  pull request posted as #798/#799 with M-1 to M-3; following them is the open item above.
- [x] 2026-11-01 TD-14 **The example coin-cell-led at its next `edakit gate --easyeda`:** routed and released again, A4, A5,
  B1, B3, B7 and C4 hold, M-5 signed for the new fab hash (e3e1290).
- [x] 2026-11-01 TD-13 **LT-9, the led-bar example on real footprints:** the placement plan fits its LCSC footprints, the
  Pico 2's pins in `symbol_differs` (dc07193).
- [x] 2026-11-01 TD-12 **The KiCad live test with the owner:** all seven steps, LT-1 to LT-11 in the concept (4dbf4fc).
- [x] 2026-11-01 TD-11 **The bell's L.9 and its T-Display on the data path:** done in the bell's session, its branch
  edakit-current (2dd5f55).
- [x] 2026-10-31 TD-10 **The notices after the merge into main:** the bell and pytree-27 told of F-6's placeholder warning
  and the walkthrough gaps' changes to their gate; the plugin follows main at 868e942 (59b62db).
- [x] 2026-10-31 TD-9 **Live runs of design as text:** 2.2 (`[routing] drc_rules` "write"), 3.6 (the way back into the
  PCB), M-6 not voided by a footprint, and what was found on the way – built (bc44fa7).
- [x] 2026-10-31 TD-8 **The owner's look at the footprint in EasyEDA:** looked at, the throwaway projects edakit-probe-*
  deleted (14e98bc).
- [x] 2026-10-31 TD-7 **B2, the hole unit of `PCB_PrimitivePad.create`:** read back in live run 3.6 (59e0939).
- [x] 2026-10-31 TD-6 **W.2 to W.5, the wired schematic:** merged into main, the concept done (81cd5f2, 2d475fc, d379775,
  868e942).
- [x] 2026-10-31 TD-5 **D.1, the style guide and the glossary:** with test_style.py and test_references.py (2b37669).
- [x] 2026-10-31 TD-4 **Walkthrough 2, the 555 blinker on KiCad:** the run up to RELEASED (123389b); boards not ordered –
  the owner's decision at the release (7999d5a).
- [x] 2026-10-31 TD-3 **ODB++ on the KiCad tool chain:** `kicad-cli` exports it for a maker that takes it (82039a8).
