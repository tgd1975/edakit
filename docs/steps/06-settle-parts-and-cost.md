# 6 Settle parts and cost

After this step you know that every part can be bought and what the boards will cost.

## What you do

Wait a minute. Claude asks JLCPCB about every part it would place, with `edakit stock`, and prices the order:

```text
$ edakit cost
board main, 44 × 44 mm: Economic PCBA ([release] assembly.sides top: one side)
…
  board main                                         20.65 USD
  as Standard:                                       50.23 USD (fees 38.93, parts 0.60)
```

## What you are asked

Only where a part is a problem: out of stock, or of a class that makes the assembly dearer. Claude names the ways out:
another part, a dearer assembly, or the part soldered by you.

## What you decide

- Who solders what. A part you solder yourself leaves the list for the assembler, and `edakit order` writes it apart:

  ```text
  $ edakit order
  bom_main.csv: 3 lines for the assembler (5 boards)
  cart_lcsc.csv: 1 line, C70377 x 5
  hand_assembly.md: 1 part by hand, 0 items off the board
  ```

- The quantity, and the shops you buy from besides LCSC.
- Whether the cost fits your budget.

## What you have

`hardware/stock.json`, what the shop had on the day it was asked. It ages, and the checks ask for a fresh one before
an order. Next: [Draw and hand over](07-draw-and-hand-over.md).

## Read on

- The walkthrough: [Stock and cost](../../handbook/17-walkthrough.md#177-stock-and-cost)
- The handbook: [Parts at the shops](../../handbook/04-parts-database.md#42-finding-parts)
