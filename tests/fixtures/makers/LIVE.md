# Live runs of the skill cart, 2026-11-01

A copy of `examples/blinker-555` with `[cart] makers = ["jlcpcb", "pcbway", "eurocircuits"]`, released (run
20261101-000246, KiCad tool chain), each order put into the maker's cart in the owner's accounts with Claude in Chrome
and nothing ordered. What each folder `<maker>/live_2026-11-01/` holds: the job, what the page showed (quote.json,
quote_page.txt), edakit cart check (check.md), the regulatory review at the order, the cart line and the order record.

- 5.7 JLCPCB: every check passed, "SAVE TO CART" pressed, order record written. Found on the way: the page shows
  "60 x 28 mm" for "60.00 x 28.00 mm", names only the Gerber upload (as the project), asks the ship-to country at
  checkout only, opens a dialog "Confirm Parts Placement" (auto-confirmed after 72 hours unless ticked off), wants a
  customs "Product Description".
- 5.12 PCBWay: every check passed, "Save to Cart" after the owner's "Agree", the files uploaded in the cart (not
  submitted for review), order record written. Found: no part matching before the cart, files only after it, a cart
  line named by the board's size, a tick "change HASL to ENIG at our discretion".
- 5.8 Eurocircuits: stopped, as the skill must, at "Board thickness" – 1.6 mm is not among Eurocircuits' thicknesses.
- 5.10 AISLER: SYNC.odb's two spots were its own rounding (fixed). The first try (aisler/live_2026-11-01/first_try.md)
  stopped at the parts: the ODB++ carried LCSC numbers only, and AISLER matches by MPN – one part of ten assigned.
  The second (run 20261101-084718, with MPN and Manufacturer in the footprints; job, quote, page text and check in
  aisler/live_2026-11-01/): seven parts assigned by "mpn", three whose MPN AISLER lists twice by the release's
  manufacturer, BT1 and SW1 excluded; /checkout set to Amazing Assembly, 1.6 mm, HASL Lead Free, 35 µm, green, white,
  quantity 5 – ORDER.form passed. Stopped at ORDER.parts: R1 and R2 out of stock at AISLER, so no price; the BOM price
  for 5 was €175.24.
  The third (run 20261101-102149, aisler/live_2026-11-01/price/): R1 and R2 swapped in the copy for YAGEO
  RC0805FR-07750KL and RC0805FR-07200RL, M-1, M-5 and M-6 again by the agents; every part assigned (R1, R2 by "mpn"),
  /checkout at Amazing Assembly, quantity 5: €348.03 net, VAT 19 % €66.13, €414.16, dispatch 2026-11-25. Every check
  passed, the review "Order: OK"; stopped before "Continue to Checkout".
