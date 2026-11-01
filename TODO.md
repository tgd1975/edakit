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

## For the owner

What only the owner can do – an account, a payment, an OK, hardware in hand, a click in Claude Code –, one line each
(`- [ ] TD-<n> **What:** command or link – why. *(session)*`), ticked off at once; the session that wrote a line deletes
it once ticked. Every line has an ID that is counted up and never reused; next free ID: TD-3. The items further down
that wait for the owner stay where their step is.

- [x] TD-1 **Update the edakit plugin:** in Claude Code `/plugin` → edakit → Update, then `/reload-plugins` or a restart in
  every running session – installed is 868e942 of 31.10.; `/reload-plugins` alone only reloads that one. Why: the
  bell's hook and Makefile use the plugin, and 868e942 knows neither W.2–W.4 nor the electrical hash M-6 now hangs on.
  *(edakit-be, automatic-christmas-bell-b3)*
- [x] TD-2 **Read the circuit-language sketch in peace:** `docs/concepts/new/circuit-language.md` (the bell as a language
  and as TOML), six open decisions. No date, nothing waits on it. *(edakit-29)*

## Ordering at the manufacturer (phase 5, [ordering.md](docs/concepts/done/ordering.md))

Built offline and tested on recorded data on 2026-10-30, merged into main the same day: the order form as keys, the
makers' profiles (JLCPCB, PCBWay, Eurocircuits, AISLER), the checks per maker, `edakit cart fields|prepare|check|
actual` with B-1 to B-7, the order record, the skill cart, the review at the order, ODB++ with F-7. Run live at the
four makers on 2026-10-31 and 2026-11-01, into the cart and nothing ordered ([LIVE.md](tests/fixtures/makers/LIVE.md)).

## What edakit needs from EasyEDA Pro and easyeda-mcp-pro ([upstream/README.md](upstream/README.md))

The requirements E-1 to E-16 on EasyEDA Pro and M-1 to M-8 on easyeda-mcp-pro, gathered on 2026-11-01 under the
owner's rules there: no click because of the API, no self-extended MCP server, the latest state checked first.

- [ ] **On the owner's computer – the newest versions live:** EasyEDA Pro 3.2.209 (3.2.206 is installed) and
      easyeda-mcp-pro 1.6.0 (the pin is 1.4.0) with the patched extension of the same version; E-1 to E-4 and E-7
      checked again, the self-test, one gate run of the example; M-6: `scope: "all_pages"` of
      `easyeda_schematic_components` instead of focusing page after page, and the BOM's duplicates. Then the pin raised
      in `mcp-server.sh`.
- [ ] **The six issues with their pull requests at easyeda-mcp-pro, posted on 2026-11-01** – #792/#793 (stale sweep),
      #794/#795 (schematic PDF), #796/#797 (return depth), #798/#799 (ODB++), #800/#802 (createProject), #801/#803
      (pick-and-place as CSV): follow them, answer review comments on the fork's branches, rebase when `main` moves;
      the comment "I agree to the Contributor Permission v1 in CONTRIBUTOR-LICENSING.md", when the maintainer asks for
      it, from the owner. M-6 not posted – #539 has met it as far as EasyEDA's API lets it (upstream/README.md).
- [ ] **On the owner's word – post:** E-1 to E-16 at easyeda/easyeda-api-sdk after the live check above – to #33, #34, #36, #38 and #39 as comments. Before
      each the check of "The latest state".
- [ ] **When a release brings M-2 to M-4:** pin raised, the original extension, `bridge-extension-patch.sh` and
      `odb-tool-patch.mjs` removed, handbook 2.4, 2.5 and 9.1 follow.

## The documentation for its readers ([documentation.md](docs/concepts/new/documentation.md))

Decided on 2026-10-31; D.1 (the style guide, the glossary and their tests) built the same day. D.2 to D.7 not before
the other todos in this list are done: the documentation describes what they leave behind.

Each step starts on the owner's word, one per branch, under the concept's rules for what the automation reads –
sources, data and code untouched; a text that is generated or used elsewhere stays; unsure, ask:

- [ ] **D.2** The entry layer: the README as the start page of one screen with the case for edakit (what you bring, what
      edakit brings, the walkthrough's count), `docs/quickstart.md` with its test, `docs/how-it-works.md` with the
      pipeline drawing and a transcript; `test_plugin.py` pointed at the page that lists skills and agents.
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
- [ ] **D.9** `docs/projects.md`, the gallery: the example and the bell now; pytree's entry with the information and the
      pictures the owner picks (needs the owner – the repository stays private); the tiny jukebox, the pedal and the
      steering wheel each after its conversion to edakit (`/edakit:new-project` with the inventory, a project of its
      own), on the owner's word.
