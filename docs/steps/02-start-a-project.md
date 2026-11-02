# 2 Start a project

After this step your repository holds a project: its settings, an empty circuit and your first decision.

## What you do

Open Claude Code in the repository of your project. An empty one is fine. Then type:

```text
/edakit:new-project my-board main
```

The first word names the project, the second its board.

## What you are asked

All questions come at once, in Claude Code's form, the recommended answer first. Among them:

> - A PCB, or a development board with wiring?
> - Drawn in EasyEDA Pro or in KiCad?
> - Who makes and assembles the board?
> - How many sets?
> - A budget, a currency?
> - Private, a gift, or for sale? Where is it used?
> - What must the circuit do?

A question you cannot answer yet keeps its default. Claude names it in its report.

## What you decide

Every answer is yours. EasyEDA Pro is the default program for the board, and KiCad is the other choice. Claude says
what each means for your project. The purpose matters most: it sets how deep the legal review of a later step goes.
That review is support, not legal advice. Nothing in it is legally guaranteed, and it makes no promise to be correct.

Then Claude shows every file and every setting with the answer behind it. Nothing is written before your OK.

## What you have

- `edakit.toml`, the project's settings;
- `hardware/graph.toml`, the [hardware graph](../glossary.md#hardware-graph): the circuit as text, empty but for
  its purpose;
- `docs/decisions.md`, your answers as the first decision, D-1;
- a git hook that runs the checks on every commit, and the settings that load the plugin in every session.

Next: [Say what it must do](03-say-what-it-must-do.md).

## Read on

- The walkthrough: [Set up](../../handbook/17-walkthrough.md#172-set-up)
- The handbook: [A project](../../handbook/02-setup.md#27-a-project)
