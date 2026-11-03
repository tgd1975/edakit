# The parts order: LCSC's cart, several projects in one, shipped with the boards

Status 2026-11-03: done – decided on 2026-11-02 in a decision round in Claude Code's form (decisions 1 to 3 as
recommended, 5 against the recommendation – the skill enters the warehouse address –, 4 decided by Claude and
confirmed) and built: step 1 merged (#203), steps 2 and 3 merged as edakit 1.1.5 (#265). Left is the live run of the
skill cart's modes `parts` and `combine` at the next parts order, which also records the BOM tool's labels and sets
`recorded` in `edakit/suppliers/lcsc.toml` – TODO.md TD-111.

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

## What the shipping cost on 2026-11-02

The first combined order – at JLCPCB the tree with assembly and two bare bell boards (1,340 g), at LCSC 26 lines of
THT parts – to Austria. Prices in USD as the checkouts showed them. No order numbers, addresses or account data in
this repository (the owner, 2026-11-02).

| Route | Shipping | Lead time | Duties |
|---|---:|---|---|
| JLCPCB direct, DHL Express (cart estimate) | 30.57 | 2–4 working days | VAT and DHL's fee at delivery |
| JLCPCB → LCSC Hong Kong, S.F Express (paid) | 6.54 | 2–5 working days | – |
| LCSC alone, Global Direct Standard Line | 18.37 | 7–15 working days | "Tariff" 27.85 prepaid |
| LCSC alone, 4PX / Singapore Post | 20.70 / 29.95 | not read | not read |
| LCSC alone, FedEx IE / UPS / DHL | 40.83 / 41.97 / 52.19 | 2–5 working days | not read |
| **Combined (LCSC 1,500 g + JLCPCB 1,340 g), cheapest express** | 56.94 | 2–5 working days | no "Tariff" line |
| **Combined, DHL Express (paid)** | 68.40 | 2–5 working days | no "Tariff" line |

What follows from it:

1. **Combining is not cheap by itself.** Together the parcel weighed about 2.8 kg; LCSC then offered only UPS, FedEx and
   DHL ("the original shipping method failed to apply … exceeding the weight limit"). Paid: 6.54 + 68.40 = 74.94 for
   shipping, against 48.94 for the two cheapest separate routes – which would have brought the parts 7–15 working
   days later. Combining buys speed and one parcel, not a lower price.
2. **The decision falls before the prices are known.** JLCPCB's address cannot be changed after its checkout; LCSC
   shows the combined prices only after JLCPCB is paid ("Combine Orders" appeared about 20 minutes after the payment).
   So the comparison has to be estimated from the weights before JLCPCB's checkout: JLCPCB's cart shows its weight,
   LCSC's cart its own; above about 2 kg together, expect express only.
3. **LCSC's weight estimate is high.** 1,500 g for 26 lines of LEDs, resistors and headers – most of the combined
   weight, and what pushed the parcel off the cheap lines. Worth asking LCSC or reading the order's real weight
   afterwards.
4. **Duties move with the route.** LCSC's Global Direct line prepaid a "Tariff" (27.85); the express routes did not –
   import VAT and the carrier's handling fee come at delivery. Compare totals with that in mind (an assessment, not
   legal advice).
5. **Pick the method before paying.** After combining, LCSC asked to choose the method again, and DHL Express
   (68.40) was paid instead of the cheapest express (56.94).

For proposal 4 this means: `edakit cart prepare` prints the weights of both carts and the routes to compare – JLCPCB
direct, LCSC alone, combined – before the JLCPCB checkout, and the skill reads LCSC's recalculated methods after
combining and names the cheapest one that meets a date the project gives.

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
2. `edakit/suppliers/lcsc.toml`, `edakit order check`, the skill cart's LCSC part (decision 3) – built 2026-11-02,
   branch `parts-order-lcsc`: `edakit order` writes `basket.json`, the check is ORDER.basket, the skill's mode
   `parts`. The profile is provisional: the BOM tool's page (`https://www.lcsc.com/bom`, read 2026-11-02) is drawn by
   JavaScript, so "Add to Cart" comes from the first order and the skill presses it only after the owner confirmed the
   label. A live run at the next parts order, nothing ordered, records the labels.
3. The combined shipment in the job and in the skill (decision 5) – built 2026-11-02 on the same branch: `[combine]`
   in the profile (the address and conditions from LCSC's help page, read 2026-11-02, the warehouse's recipient
   instead of the owner's name), `combine` in the job at JLCPCB when the basket has LCSC lines, both carts' weights
   and the routes printed by `edakit order check`, after combining the cheapest of LCSC's methods arriving by the new
   key `[cart] needed_by`; the skill's mode `combine`, handbook 8.4 and the skill's "Never" changed with it. Not in
   `order.md`, as proposal 4 had it: that file is a release file inside the fab hash, written at the gate run – the
   step lives in the job and its print, which come after the release.
