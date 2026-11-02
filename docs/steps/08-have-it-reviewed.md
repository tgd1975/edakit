# 8 Have it reviewed

After this step independent reviewers have read your circuit, and their judgement counts for exactly the files they
read.

## What you do

Start each reviewer in a session of its own when Claude asks for it. The session that designed does not review. Each
reviewer is an [agent](../glossary.md#agent) of the plugin and changes no file. Five checks are signed, by a reviewer or by you:

| Check | What | Who |
| --- | --- | --- |
| M-1 | the critical parts against their datasheets, a second time | the reviewer electrical-reviewer |
| M-6 | the circuit against EU law, for its purpose | the reviewer regulatory-reviewer |
| M-5 | the board: can it be made, does it look right | the reviewer pcb-reviewer, after the layout |
| M-2 | the parts' orientation in the manufacturer's preview, before you pay | you |
| M-4 | every delivered board, tested | you |

The legal review is support, not legal advice. Nothing in it is legally guaranteed, and it
makes no promise to be correct.

## What you are asked

Each reviewer returns numbered notes. They come to you as one round of questions, as in
[Decide on what was found](05-decide-on-what-was-found.md).

## What you decide

Each note: fix it, or keep it with a reason. You also decide what the reviewers cannot, such as who uses the board.

## What you have

Each [sign-off](../glossary.md#sign-off) in `hardware/signoff.json`, bound to the exact state of the files it judged.
Any later change of the circuit makes M-1 and M-6 count no longer, and both reviewers look again. Next:
[Lay out the board](09-lay-out-the-board.md).

## Read on

- The walkthrough: [Reviews](../../handbook/17-walkthrough.md#179-reviews)
- The handbook: [Who signs what](../../handbook/08-release-gate.md#82-hashes-and-sign-offs)
