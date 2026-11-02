# 3 Say what it must do

After this step one file holds what your circuit must do, in your words, each point with how it is tested.

## What you do

Tell Claude your idea, or type `/edakit:requirements`. The form of the last step starts it when you answer "now".

## What you are asked

Claude asks about the people, the use and the limits:

> - Who uses, builds, gets it? Who must not notice it?
> - How does one use go, step by step?
> - Where does it stand, where does the power come from, how often and how long does it run?
> - What does one press, see, hear?
> - What must never happen?

A vague word comes back as a question with a suggestion, until it is your number. In the walkthrough "lights" became
1 mA, and "a used cell" 2.5 V.

## What you decide

Claude writes drafts. Only you approve one: you set its status to `accepted`, or you tell Claude to. You also choose
how binding it is: `must` holds the order back until it passes, `should` warns, `may` informs.

## What you have

`hardware/requirements.toml` with your [needs](../glossary.md#need) and the
[requirements](../glossary.md#requirement) that follow from them. `edakit req` shows one with where it comes from:

```text
$ edakit req R-1
R-1  requirement, must, accepted – hardware/requirements.toml
  from    N-1  need, accepted: Press the button and the LED lights; let go and it is dark.
  text    While SW1 is pressed, D1 carries at least 1 mA – from a fresh CR2032 down to one used to 2.5 V.
  verify  rows SIM.state * D1 LED on
          accept press SW1 with a fresh cell: D1 lights; let go: D1 is dark
```

The rows are results of the simulation. The last line lands on the list you test once the boards arrive. Next:
[Design the circuit](04-design-the-circuit.md).

## Read on

- The walkthrough: [What it must do](../../handbook/17-walkthrough.md#173-what-it-must-do)
- The handbook: [Requirements](../../handbook/03-hardware-graph.md#36-requirements)
