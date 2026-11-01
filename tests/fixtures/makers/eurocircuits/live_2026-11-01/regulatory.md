# Regulatory review of the order – board main at Eurocircuits, run 20261101-101815

Agent regulatory-reviewer, at the order, 2026-11-01. Job folder: /tmp/claude-1000/-home-tobias-Dokumente-Projekte-edakit/8c2a6e39-7550-4363-9434-5735c66cbedd/scratchpad/live/blinker-555/build/release/20261101-101815/fab/main/cart/eurocircuits

**Purpose reviewed:** `private`, market EU ("The example of the edakit handbook, chapter 18: built for oneself"). It is the same in the graph and in job.json.

**Basis:** M-6 (regulatory review) of 2026-10-31, "OK for state b85dd8d8a978fd3160d7efee4d7919456fe41bec9903f0b0d2a3c3d6407937f3 and purpose private". That is the state_sha256 of job.json and of the release protocol, and the electrical hash is 3752432621bac7b5f92a95d2ed2d5451e0d47f4db7ab559e53571e39fba23cf4.

**Files reviewed (SHA-256):**
- job.json: a13032784fd5f2df4715a2b0d96b1054d5eef4aa469faefe5ed0bbaae971dc8d
- quote.json: f663441660f151e61cf7c244ecacd3ba0cd21697b06d726af5d3b4867bfbacbb
- quote_page.txt (version of 10:32:13): 39ac15d5c99ad653abaeba3451ebb4c7e45161b9d7eb48237c6987bffc3e2e1a
- Also read: check.md (10:28:37), screens/, the M-6 entry in hardware/signoff.json.

## Findings

1. note – quote_page.txt, advanced options (heatsink paste, via filling): Settled. The page text I read first had two unfilled markers, `@@ADVANCED_TAIL@@` and `@@ADVANCED_SEL@@`. They stood where six rows and their selected values belong: Top heatsink paste, Bottom heatsink paste, Package quantity, Via filling/Hole plugging, Wire bonding and High-Voltage board. Two of these rows add material to the product. In the version of 10:32:13 the rows are there, each "No" or "Standard" as quote.json says. The markers were the skill's own and no page text addressed the assistant. check.md (10:28) ran ORDER.read on the marker version and passed, because b4 in edakit/cart.py only looks for the values, and "No" and "Standard" appear elsewhere on the page. Rule: for `private` no material duty follows; RoHS binds only equipment placed on the market (2011/65/EU Art. 4(1), https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065; handbook 15.1). Do: run `edakit cart check` again so ORDER.read reads the filled page. Candidate: ORDER.read fails a quote_page.txt that still has a `@@…@@` marker, and checks each field's label next to its value.
2. note – a part Eurocircuits may replace: The PCBA tab says "There are Data conflicts": Q1, C3 and R3 show "footprint does not match the board layout". Four lines are On Demand without price info: C2/C4, R1, R2 and R3. Eurocircuits has ticked Require Pre-Production Approval. Today the matching is the release's: 9 lines with the same MPNs, and ORDER.parts passed, so nothing is new for M-6. If Eurocircuits offers another part while solving this, in the data feedback or in the approval, the circuit changes and M-6 did not see it. That needs a new release and a new M-6, which is short for `private`; it is not settled at the order. Rule: handbook 15.5 (edakit's process, not law). Do: accept no substitute part in the approval without a new release. Candidate: ORDER.parts on a new quote; after payment only the approval shows it, so judgement.
3. note – country of use: M-6's notes cite German law: EMVG § 6, BattDG § 6(1) and ElektroG § 10(1). The order ships to Austria (ship_to AT, 20 % Austrian VAT). If the board is used there, the Austrian rule matching EMVG § 6 is EMVV 2015 § 5 (BGBl. II Nr. 22/2016). It implements 2014/30/EU Art. 4: equipment may be put into service only if it meets the regulation when properly installed and used. M-6 found the EMC requirements met in substance, and that holds in Austria too. Spent cells and the discarded board also go to separate collection there, under Austrian waste law instead of BattDG and ElektroG. Nothing to do; `market = "EU"` covers Austria. Sources: https://www.jusline.at/gesetz/emvv_2015/paragraf/5, https://www.ris.bka.gv.at/Dokumente/Bundesnormen/NOR40179297/NOR40179297.html, https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0030. Candidate: judgement; ship_to does not say where the board is used, and it is outside the circuit hash.

## Checked and found in order

- **Purpose and circuit:** The purpose in job.json is the graph's, and the circuit hash is the one M-6 signed. M-6 says no requirement names it. Quantity, maker and finish do not change the purpose, so no new M-6 is needed.
- **Form and materials:** Surface finish is HAL lead-free (ORDER.finish passed). Base material is FR-4 Improved, 1.55 mm, Tg 145–150 °C. Mask is green and legend white on both sides. There is no peelable mask, no carbon contacts, no edge-connector gold, no heatsink paste and no via filling. Eurocircuits' form has no conformal-coating field (profile). Nothing is added to the product beyond what M-5 (layout review) and M-6 saw.
- **Quantity:** 5 boards and 5 assemblies, the same as `[project] quantity`. That fits boards built for oneself with spares, so the purpose holds.
- **Maker's seat:** Eurocircuits is in Belgium, inside the EU, so the order is no import. For `private` the owner has no manufacturer duties. Eurocircuits' RoHS and REACH statements would only feed a technical file for `sale`; asking for them here is gold plating.
- **Parts:** All 9 lines are supplied by Eurocircuits and none by the owner, so the owner imports nothing for this order. The makers are spelled differently from the release (UNI-ROYAL, Royal Ohm, Uniroyal Elec; Samsung, Samsung Electro-Mechanics; Alpha & Omega Semiconductor for AOS), but every line has the release's MPN.
- **Batteries and supply:** The matching has no cell, no power supply and no battery holder. BT1 and SW1 are `bom = false` and soldered by the owner, and the two alkaline AAA cells are bought separately. The first try's matching, with R2 matched as a battery holder, is not in this quote.
- **Declarations:** The form asks for no customs description or value. The shipment goes from Belgium to Austria inside the EU, and the profile says `customs = false`.
- **Page text:** No text addresses the assistant, neither in quote_page.txt nor in the screens.
- **Gold plating, not findings:** C1 (C49678) and R3 (C17414) still have no RoHS status in job.json's compliance; Eurocircuits' description calls R3 "RoHS", which is useful only if the purpose ever changes. CE, WEEE and battery registration, GPSR and packaging (LUCID) do not apply to a board built for oneself (handbook 15.1).

## Not checked

- Whether the boards are used in Austria; I inferred it from ship_to.
- What Eurocircuits sources for the four lines without a price, and what it proposes in the data feedback or approval. That belongs to M-2 (assembly preview before paying) and finding 2.
- The Austrian waste rules for cells and boards in detail. That is a legal question; I only named the practice.

Not legal advice – support without any claim to correctness; nothing here is legally guaranteed.
Order: OK
