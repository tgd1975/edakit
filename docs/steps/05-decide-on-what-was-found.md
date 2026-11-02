# 5 Decide on what was found

After this step every result of the checks is fixed or kept with a reason, and every choice has its number.

## What you do

Answer. Claude gathers what the checks and the simulation left open and asks it in one
[decision round](../glossary.md#decision-round).

## What you are asked

Each [finding](../glossary.md#finding) is a question in Claude Code's form. It says what is wrong and where, and what
happens if nothing is done. Then come the options, the recommended one first. In the walkthrough one read like this:
the cell can go in upside down. Add a diode in series, which costs a third of a volt? Or leave it, since the LED
blocks by itself?

You pick an option, or you answer in words: `ack`, `you decide`, or `no idea what this is about`, and Claude explains
it again. What Claude settled by itself comes last, in one question to confirm.

## What you decide

Cost, looks, how it is used, and what a fault may do. A deviation without a real consequence is not asked.

## What you have

Each answer as a numbered entry in the [decision log](../glossary.md#decision-log), `docs/decisions.md`: the
decision, your reason, the date. A result you chose to keep carries its reason in the circuit, and every check shows
it:

```text
$ edakit check
PATH.reverse – reverse polarity blocked: 1 error (accepted)
      accepted: a cell upside down drives R1 and D1 backwards: D1 blocks, 3.2 V against its VR of 5 V – …
```

Next: [Settle parts and cost](06-settle-parts-and-cost.md).

## Read on

- The walkthrough: [What the checks found](../../handbook/17-walkthrough.md#176-what-the-checks-found)
- The handbook: [Working with Claude](../../handbook/11-working-with-claude.md)
