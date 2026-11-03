# 10 Order the board

After this step your boards are ordered, paid, delivered and tested.

## What you do

Ask for the [release](../glossary.md#release). Claude runs every check again, now on the files that go to the
manufacturer. Only a run that ends with `RELEASED` may go out.

Then `/edakit:cart` fills the manufacturer's form in your Chrome, with Claude in Chrome. Every field comes from your
project:

```text
$ edakit cart fields
PCB
…
  PCB Qty                   5                           [project] quantity quantity = 5
  PCB Thickness             1.6 mm                      edakit       thickness_mm = 1.6
…
```

Claude reads every field back, checks the quote against the estimate and stops at the cart.

## What you are asked

Once: the country you ship to and the shipping method.

## What you decide

- Ordering and paying. Nothing in edakit orders or pays.
- M-2: the parts' orientation in the manufacturer's preview, before you pay.
- M-4: when the boards arrive, you test each one against the list the last run wrote.

For M-2 JLCPCB shows the board with its parts as they will be placed, here the walkthrough's:

![JLCPCB's placement preview of the walkthrough's board: D1, R1 and SW1 placed, the cell holder's pads bare for soldering by hand](../../examples/coin-cell-led/docs/jlcpcb_assembly_main_top.png)

The cell holder BT1 comes from LCSC, and `edakit order` puts it into the cart. You solder its two tabs yourself, then the board is done:

![The walkthrough's finished board in EasyEDA's 3D view: the cell holder BT1 soldered, below it the button SW1, the LED D1 and the resistor R1](../../examples/coin-cell-led/docs/board_main_3d.png)

## What you have

Boards in your hand, and a record of the order in `hardware/orders/`. Once paid, `edakit cart actual` puts the real
cost beside the estimate.

## Read on

- The walkthrough: [Release, order, acceptance](../../handbook/17-walkthrough.md#1712-release-order-acceptance)
- The handbook: [Ordering](../../handbook/08-release-gate.md#84-ordering-at-the-manufacturer-up-to-the-cart-you-order-and-pay)
