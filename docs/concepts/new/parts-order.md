# The parts order: LCSC's cart, several projects in one, shipped with the boards

Status 2026-11-02: decided the same day in a decision round in Claude Code's form – decisions 1 to 3 as recommended,
5 against the recommendation (the skill enters the warehouse address), 4 decided by Claude and confirmed. Nothing built
yet; each step starts on the owner's word.

## Why

edakit takes a board up to the maker's cart (handbook 8.4, `docs/concepts/done/ordering.md`). The parts a project
buys elsewhere stop at a file: `edakit order` writes `cart_lcsc.csv` per project, and the rest happened by hand on
2026-11-01/02:

1. **Several projects, one order.** The tree (pytree) and two bell variants went into one JLCPCB order. Their LCSC
   lists were three files – pytree's hand-written `docs/bestellung/…/lcsc_bom.csv` with reserve, the bells' generated
   carts without – merged by a throwaway script, the same part summed (C2895493, C2895495).
2. **A better part found at the order.** The owner asked for notched (breakable) female headers instead of the smooth
   1x15 and 1x12 ones; the agent part-selector found C2916940 (XKB X5511FV-40-C85D30-1150, 1x40, 8.5 mm). The change
   of an `[[extra]]` waits for the owner – nothing in edakit asks the question at the order.
3. **The combined shipment.** LCSC ships a paid JLCPCB order with its own when the JLCPCB order goes to LCSC's Hong
   Kong warehouse – an address entered at JLCPCB's checkout, unchangeable afterwards – and the LCSC checkout ticks it
   under "Combine Orders" (LCSC help article "Combine Your LCSC and JLCPCB Orders", read 2026-11-02). Same currency,
   same customer ID, one JLCPCB order only, paid but not packed. These steps were in pytree's order list and in a chat;
   edakit knows none of it.
4. **The LCSC cart was not empty.** It held 25 lines from earlier work. An upload adds to them; nothing showed which
   lines are this order's.
5. **Quantities.** pytree rounded by hand to LCSC's minimum and step quantities with reserve; the bells' carts hold the
   exact need ("5 + 0"). `order` in a parts entry knows `moq` and `step`, no project used them.

By the yardstick (`docs/concepts/done/design-as-text.md`), points 1, 3 and 4 live only in someone's head today.

## Proposal

### 1. One basket across projects – `edakit order --with`

`edakit order --with ../pytree/edakit.toml --with variants/esp32tht/edakit.toml` writes the carts of several projects
as one: each supplier's lines summed by its code, the comment naming each project and designators ("Baum: 20 …
D18 D22 | Glocke THT: 5 … LED1"). The hand-assembly lists stay per project. The basket is written to `--out`, by
default the first project's `<artifacts>/order/`.

### 2. Reserve and the supplier's quantities

`[order] reserve` (per cent or pieces, by default 0) and the parts entry's `moq`/`step` round each line up; the
comment says "need + reserve". pytree's hand-made list becomes generated.

### 3. LCSC's cart with the skill cart

A supplier profile `edakit/suppliers/lcsc.toml` like a maker's: start page (BOM Tool), columns, the cart button
("Add to Cart"), the `never` list (Checkout, Pay, Place Order). The skill uploads the basket in the BOM Tool, reads every
line back (number, quantity after LCSC's rounding, stock, price), and `edakit order check` holds it against the basket:
each part there, quantity ≥ need, none out of stock, no line replaced. Lines already in the cart are listed apart and
never touched (the rule of 2026-10-30: nothing in the cart is changed or deleted) – the owner decides about them.

### 4. The combined shipment as a step the job names

When the planned maker is JLCPCB and a basket has LCSC lines, `edakit cart prepare` adds to the job and to `order.md`:
"ship to LCSC's warehouse – one checkout for all boards, then LCSC's checkout: Combine Orders", with the warehouse
address from a profile key (`[combine]` of `lcsc.toml`, with the date and page it was read). The skill enters that
address at JLCPCB's checkout and reads it back (decision 5) – the one exception to the rule of 2026-10-30 that the
checkout stays closed: it chooses no payment method, no coupon, and presses nothing that orders or pays. Only LCSC's
warehouse, never the owner's or anyone else's address. After the owner's payment it checks on the order page that the
JLCPCB order shows the warehouse, and at LCSC's checkout ticks the JLCPCB order under "Combine Orders" – stopping
before "Submit order".

### 5. A part question at the order

The skill asks before the LCSC cart whether an `[[extra]]` or bought part has a better variant the owner named before
(a project key `[order] prefer` with the reason) – or this stays a chat matter. Open, see decision 4.

## Decisions (the owner, 2026-11-02)

1. **Basket across projects:** built as `edakit order --with` (proposal 1). As recommended.
2. **Reserve:** as recommended – and already there when building step 1: `[project] spare_pct`, `spare` on a
   component or `[[extra]]`, and `moq`/`step` in a parts entry's `order` (handbook 8.4), so no `[order] reserve`.
   LCSC's BOM tool rounds every line to its own minimum on the upload (seen 2026-11-02: 100 Ω 10 → 50); edakit
   need not know LCSC's minimums for the cart, only for the cost estimate.
3. **LCSC cart by the skill:** the skill fills it and stops before the checkout, lines already there only reported
   (proposal 3). As recommended.
4. **Part questions at the order:** left to the chat – a part change is a hardware change (skill hardware-change); no
   `[order] prefer`, proposal 5 dropped. Decided by Claude, confirmed by the owner.
5. **The warehouse address:** the skill enters it at JLCPCB's checkout (proposal 4) – against the recommendation to
   print it only. The checkout opens for that address alone; payment, coupon and the order button stay the owner's.

## Order of work

1. `edakit order --with` (decision 1) – built 2026-11-02, branch `order-basket`; the reserve needed nothing new.
2. `edakit/suppliers/lcsc.toml`, `edakit order check`, the skill cart's LCSC part (decision 3) – a live run at the next
   parts order, nothing ordered.
3. The combined shipment in the job and in the skill (decision 5) – handbook 8.4 and the skill's "Never" changed with
   it.
