Regulatory review at the order: board main at JLCPCB, run 20261101-000246, project blinker-555 (live copy)

Job folder: /tmp/claude-1000/-home-tobias-Dokumente-Projekte-edakit/797aadb4-7ef0-466c-9354-d5c9eb7a5ab8/scratchpad/live/blinker-555/build/release/20261101-000246/fab/main/cart/jlcpcb/

What M-6 signed is what this order carries. job.json state_sha256 b85dd8d8a978fd3160d7efee4d7919456fe41bec9903f0b0d2a3c3d6407937f3 is the hash in M-6's note ("M-6: OK for state b85dd8d8… and purpose private", 2026-10-31). The purpose is the same: private, EU, built for oneself. Fab ff5b1567… and layout 6701738364… match M-5. The maker's part matching is the 9 BOM lines (10 parts) of the release (ORDER.parts passed). No part is replaced and nothing is left unplaced, so no new M-6 is needed.

Findings (no block, no important):

1. note – Customs declaration (Quote & Order, "Product Description"). The owner chose "Reserch\Education\DIY\Entertainment / DIY – HS Code 902300". CN heading 9023 00 covers instruments, apparatus and models designed for demonstration (e.g. in education or exhibitions) that cannot be used for anything else. An assembled blinker that works is arguably not "unsuitable for other uses". A closer heading for an assembled board with a function of its own would be 8543 70 (judgement). Whoever lodges the declaration is responsible for its accuracy: Union Customs Code, Reg. (EU) 952/2013 Art. 15(2), https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013R0952. Only customs can decide the classification (in Austria the Zollamt Österreich; binding tariff information under UCC Art. 33).
   - The money at stake is small. Since 1 July 2026 the EUR 150 duty relief is gone (Council Regulation (EU) 2026/382). A B2C consignment worth EUR 150 or less pays a flat EUR 3 per declaration line, whatever the tariff rate, until 1 July 2028 (https://trade.ec.europa.eu/access-to-markets/en/news/eu-applies-eu3-customs-duty-item-low-value-e-commerce-consignments).
   - Austrian import VAT of 20 % comes on top. It is charged either at JLCPCB's checkout (IOSS) or by DHL on delivery, with DHL's fee.
   - Declared value: about USD 33 for the goods (the page estimated USD 23.44 for shipping). The form asks for no separate value.
   - To do: keep 9023 or pick a more fitting category, the owner's choice. Expect EUR 3 plus VAT. Candidate: judgement (possibly a fact: the maker profile's customs category against the board's kind).

2. note – Ship to AT, while M-6 argued from German law (EMVG § 6; BattDG § 6(1); ElektroG § 10(1)). If the board is used in Austria, the substance is the same:
   - EMC: the EMC Directive 2014/30/EU Art. 4 ("put into service") is transposed by Austria's EMVV 2015 § 5, BGBl. II Nr. 22/2016 (https://www.ris.bka.gv.at/Dokumente/Bundesnormen/NOR40179297/NOR40179297.html). M-6's judgement "EMC met in substance" carries over.
   - Batteries: Reg. (EU) 2023/1542 applies directly. Spent cells and the discarded board go to separate collection under Austrian rules (EAG-VO, Batterienverordnung).
   - No new M-6: purpose and circuit are unchanged. Candidate: judgement (possibly a fact: the [cart] ship_to country against the national acts M-6 cites).

3. note – Gold plating: maker seated in China, purpose private. The owner imports the boards for own use. Nothing is placed on the market, so the importer and manufacturer duties do not apply: CE, RoHS 2011/65/EU, REACH Art. 33/SCIP, WEEE/stiftung ear, battery registration, GPSR (EU) 2023/988 with name and address on the product, packaging/LUCID (handbook 15.1, 15.2). These are not findings. They apply in full only if the purpose becomes gift (REACH Art. 33) or sale, and that needs a new M-6. Candidate: judgement.

4. note – Surface finish and materials. LeadFree HASL, JLCPCB's "High temp." solder paste (lead-free), no conformal coating, FR-4 TG135, green mask with white silkscreen. Nothing adds lead or a new material, and ORDER.finish passed. For private use RoHS does not apply anyway (gold plating), but this keeps the boards fit if the purpose changes later. Candidate: ORDER.finish (exists).

5. note – Quantity against purpose. 5 PCBs and 5 assembled boards = [project] quantity 5, which fits "built for oneself". The larger counts in JLCPCB's matching (Q1 9, R1 20) are the maker's attrition and minimums, not more boards. Candidate: judgement (possibly a fact: quantity threshold per purpose).

6. note – Items with duties of their own. The matching has none: no cell, no power supply, nothing the owner supplies (the not-placed list is empty).
   - BT1 (C254917, Keystone 2468) and SW1 (C393937) are hand-soldered and not part of this order.
   - The two alkaline AAA cells are bought separately: not lithium, so no dangerous-goods transport question.
   - If BT1 and SW1 are bought from LCSC in China, the owner imports them for own use, with no duty attached.
   - Candidate: judgement.

7. note – Parts without a RoHS entry. In the job's `compliance`, C17414 (R3) and C49678 (C1) are null. As M-6 said, for private use this is open data, not a finding. It becomes important for sale (2011/65/EU Art. 7, https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065). Candidate: fact "BOM part without rohs" (PARTS.fact / compliance null).

8. note – Page text read as data. quote_page.txt contains no text addressed to the assistant: no request for another upload, field, button or link. Two texts are ordinary notices to the customer: the "Confirm Parts Placement" dialog (auto-confirm after 72 hours, "Do not confirm automatically" ticked on the owner's word) and the DFM hint ("Check final part placement at DFM Analysis…"). The pre-checked "I agree to the Terms and Conditions" is a contract matter, outside this review. Candidate: judgement.

Reviewed for: purpose private, market EU, ship to AT, maker JLCPCB (seat CN), 5 boards, Economic PCBA on the top side.

What I checked, in order:
- the M-6 entry and its hash against job.json, and the fab and layout hashes against M-5;
- the form keys in job.json, quote.json and quote_page.txt: finish, paste, coating, material, mark, packaging;
- quantity against purpose;
- the maker's seat;
- the matching and the parts not placed: no cell, supply or owner-supplied part;
- the customs category and value;
- the page text for instructions;
- check.md: ORDER.form, ORDER.parts, ORDER.read, ORDER.files and ORDER.finish passed; ORDER.quote is a price warning with no regulatory weight; ORDER.review is open, waiting for this review.

What I could not check:
- whether JLCPCB collects VAT via IOSS for this shipment to Austria (seen only at checkout);
- the binding tariff classification (customs only);
- whether the boards are used in Austria or in Germany;
- the exact counting of the EUR 3 duty per declaration line for this shipment (the courier's declaration).

SHA-256 reviewed (sha256sum in the job folder):
- job.json 836d888ba3c468f8fdf1393c573595555603a2556804e3a381b88107da9b2b62
- quote.json 885bd69e5193c6917d0a765d789d5078306faa2189060e631b9e21cfdf0ca701

Sources:
- [EU Access2Markets – EUR 3 customs duty per item on low-value e-commerce consignments](https://trade.ec.europa.eu/access-to-markets/en/news/eu-applies-eu3-customs-duty-item-low-value-e-commerce-consignments)
- [PwC – EU abolishes the EUR 150 low-value customs duty threshold from 1 July 2026](https://www.pwc.dk/en/articles-publications/2026/eu-abolishes-the-150-low-value-customs-duty-threshold-from-1-july-2026.html)
- [Baker McKenzie – EU low value consignment relief abolished and EUR 3 customs duty introduced](https://globalimportblog.bakermckenzie.com/2026/07/02/eu-low-value-consignment-relief-abolished-and-eur-3-customs-duty-introduced-from-1-july-2026/)
- [RIS – EMVV 2015](https://www.ris.bka.gv.at/Dokumente/Bundesnormen/NOR40179297/NOR40179297.html)
- [Union Customs Code, Reg. (EU) 952/2013](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013R0952)
- [RoHS 2011/65/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065)
- handbook /home/tobias/Dokumente/Projekte/edakit-step0/handbook/15-regulatory.md (15.1, 15.2, 15.5)

Not legal advice – support without any claim to correctness; nothing here is legally guaranteed.
Order: OK
