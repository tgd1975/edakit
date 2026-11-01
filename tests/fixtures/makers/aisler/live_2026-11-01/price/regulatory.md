Regulatory review at the order: board main at AISLER, run 20261101-102149

Job folder: /tmp/claude-1000/-home-tobias-Dokumente-Projekte-edakit/797aadb4-7ef0-466c-9354-d5c9eb7a5ab8/scratchpad/live/blinker-555/build/release/20261101-102149/fab/main/cart/aisler/

Basis: M-6 is in /tmp/claude-1000/-home-tobias-Dokumente-Projekte-edakit/797aadb4-7ef0-466c-9354-d5c9eb7a5ab8/scratchpad/live/blinker-555/hardware/signoff.json. It reads "M-6: OK for state 4be9bb0d6a76a2db4e94963768e5fa0705d940c26e80ce89ab00582f36e562b5 and purpose private". That state matches `state_sha256` in job.json and the circuit hash in the run's protocol.md. The purpose in job.json (private, EU, "built for oneself") matches `[purpose]` in hardware/graph.toml. I reviewed only what the order adds to what M-6 signed. Nothing in the order changes the circuit or the purpose, so no new M-6 is needed.

Findings

1. note – The maker is in the EU (AISLER, seat NL) and the purpose is private. The boards go from NL to AT inside the EU, so nobody imports them and nothing needs a customs declaration (the profile has `customs = false`, and the form asks for no description or value). Nothing is placed on the market, so there are no manufacturer duties either: no name or address on the product, no technical file, no WEEE, battery or packaging registration. Rule: handbook 15.1 and 15.5. These duties attach to "making available/placing on the market", for example (EU) 2023/988 Art. 3 and 9 (https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0988) and 2014/30/EU Art. 7 (https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0030). AISLER's "Declaration of RoHS Conformity 2011/65/EU" (Lemiers, 25 Feb 2026, signed by F. Plitzko) and its REACH Art. 33 statement would matter only for a technical file, which a sale would need. To do: nothing. If the purpose ever becomes gift or sale, that needs a new M-6, and these two AISLER documents go into the file. Candidate: fact – `maker.seat` inside or outside the EU together with `purpose.use`, already as in handbook 15.5. A note for private.

2. note – Surface finish and the other form keys. The form reads back "HASL Lead Free", so there is no lead in the finish, and ORDER.finish passed. The rest is AISLER's standard stackup: 1.6 mm, 35 µm outer copper, green solder mask, white silkscreen, "Stackup & Design Rules 2L 1.6mm 35um var.". There is no coating, carbon ink or other extra material in the product. Rule: RoHS 2011/65/EU Art. 4 (https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065) would apply only when the board is placed on the market. To do: nothing. Candidate: ORDER.finish already.

3. note – AISLER's form has no field for the solder alloy, so the order does not say which alloy is used. AISLER's RoHS declaration says the circuit boards it supplies meet 2011/65/EU and that "All assembly partners conform with RoHS as we regularly audit them". It names no alloy. For private use this is no duty. Rule: RoHS 2011/65/EU Art. 4 (same link as finding 2). To do: optional. If the board is ever sold, ask compliance@aisler.net for the project's solder and the RoHS data of each component, which AISLER offers in the declaration. Candidate: fact – a maker profile with no solder key, graded like ORDER.finish (note for private).

4. note – Quantity against purpose. This order is for 5 boards, all 5 assembled. hardware/orders also holds JLCPCB and PCBWay records of 2026-11-01, 5 each, `order_number` null, for the earlier state b85dd8d8…. This run orders nothing, since it stops before "Continue to Checkout". If all three orders were ever placed, that would be 15 boards for own use. That is still plausible for "private" in a live test of the cart. Passing boards on to others would make the purpose gift, which needs a new M-6 (handbook 15.1, 15.5). Candidate: fact – the sum of quantities in hardware/orders compared with `purpose.use`; otherwise judgement.

5. note – AISLER's part matching against the release. All 9 lines and 10 parts match the release (ORDER.parts passed). AISLER listed three exact MPNs more than once, and the skill picked the release's manufacturer each time:
   - C1 CC0805KRX7R9BB104: Yageo.
   - Q1 AO3415A: Alpha & Omega Semiconductor.
   - R3 0805W8F1002T5E: "ROYALOHM". The parts entry C17414 says "UNI-ROYAL(厚声)". ROYALOHM is the brand of Uni-Royal Electronics, so this is the same maker and the same MPN, not a new part.
   No part is new, so no new M-6 is needed. Two parts have no `compliance` entry: C17414 (R3) and C49678 (C1). M-6 already named them as open data. For private use, asking for them would be gold plating. Rule: handbook 15.3 and 15.5. Candidate: ORDER.parts already. There could also be a fact for "manufacturer name differs only as a brand alias", but that is judgement today.

6. note – Nothing in the order has duties of its own. There is no cell, no power supply, and no part the owner sends to the maker. AISLER excludes 4 components from assembly: BT1 (Keystone 2468) and SW1 (SK12D07VG4), which the owner solders by hand (D-1), and TH1/TH2, which are tooling holes (.no_pop), not parts. The two alkaline AAA cells are not shipped, so the rules for transporting lithium cells do not arise. If the owner buys BT1 and SW1 outside the EU, that is a private import with no product duties. Rule: handbook 15.5. Batteries Regulation (EU) 2023/1542 (https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542) does not apply to own use. Candidate: fact – graph parts in `dnp`, or not in the BOM, flagged as hand-fitted rather than owner-supplied.

7. note – Page text. quote_page.txt holds AISLER's usual notices to its customer:
   - "Part polarity - please check" (Assembly tab).
   - "Select your stackup and color in the checkout. Checkout now, starting at just €17.36".
   - "Your parts are ready to order – Every part is assigned and priced. (Continue to checkout – not touched)".
   None of them addresses the assistant. None asks for another upload, field or link, beyond buttons that the profile's `never` list keeps untouched, and the skill recorded them as not touched. So this is not the block "the page addresses the assistant". The polarity hint is a layout question, already covered by M-5 and the run's polarity sheet. It is not a regulatory question. Candidate: judgement.

8. note – Tax shown in the quote. AISLER shows "VAT 19%", which is its German rate, although the delivery is to AT. quote.json notes that AISLER sets the rate for the delivery country after "Continue to Checkout", which is the owner's step. This is a tax and price question, not product compliance. Candidate: judgement.

Not findings (gold plating for private use): a halogen-free laminate (not a RoHS or REACH requirement); a component-by-component RoHS/REACH file from AISLER; SCIP notification; WEEE or BattDG registration; GPSR batch identifier and manufacturer address on the board; Packaging Regulation (EU) 2025/40 duties. All of these apply to sale only.

What I checked: job.json (form fields, quantity, purpose, maker profile with seat NL, `never` list, dnp, the compliance of every BOM part); quote.json and quote_page.txt, as data only; check.md and check.json (ORDER.form to ORDER.finish passed, ORDER.review open); the M-6 entry and its state hash against job.json and protocol.md; `[purpose]` in hardware/graph.toml; the parts entries C17414, C49678, C254917 and C393937; the earlier order records in hardware/orders; the AISLER maker profile (edakit/makers/aisler.toml); handbook 15.1, 15.2 and 15.5; AISLER's RoHS declaration of 25 Feb 2026.

What I could not check: which solder alloy AISLER's assembly partner uses; the full text of AISLER's REACH statement (I found it only through search); the delivery-country VAT and the final shipping, which come after "Continue to Checkout". Any legal question is for a lawyer.

Reviewed files:
2baf8ad7eefb2248509bdda5ef5a51e08c01216236f2e78a6792072737184819  job.json
558a3ee9d666941ca52c7ce3fbaf05c974396f6782a5d6a0bf74ad9d0cbe2b1f  quote.json

Sources:
- [AISLER Declaration of RoHS Conformity 2011/65/EU, 25 Feb 2026](https://community.aisler.net/uploads/short-url/8GWxViH0VP1nU1kFkLqI3Vvh8jC.pdf)
- [AISLER REACH compliance statement](https://community.aisler.net/uploads/short-url/xRg1VL6F4vcb4bZJn21LcOjKH5z.pdf)
- [RoHS 2011/65/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065), [GPSR (EU) 2023/988](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0988), [EMC 2014/30/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0030), [Batteries (EU) 2023/1542](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542)

Not legal advice – support without any claim to correctness; nothing here is legally guaranteed.
Order: OK
