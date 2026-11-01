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
