# 1 Install the tools

After this step Claude Code knows edakit, and your computer can run its checks and its simulation.

## What you do

In Claude Code in the terminal, add the plugin:

```text
/plugin marketplace add tgd1975/edakit
/plugin install edakit@edakit
```

In VS Code the extension has no `/plugin`. There you type the same two lines in a terminal, with `claude plugin` in
front:

```bash
claude plugin marketplace add tgd1975/edakit
claude plugin install edakit@edakit
```

Then install two programs:

- [uv](https://docs.astral.sh/uv/), the Python tool that runs edakit;
- [ngspice](https://ngspice.sourceforge.io/), the simulator, from your package manager: `sudo apt install ngspice`.

## What you are asked

Claude Code may ask you once to allow the plugin's server for EasyEDA. Say yes. A circuit does not use it.

## What you decide

Nothing else for now. A circuit runs without EasyEDA Pro and without KiCad. You install one of them only for a board,
when you come to [Lay out the board](09-lay-out-the-board.md).

## What you have

Claude Code with the plugin, and the command `edakit` in every session. Next: [Start a
project](02-start-a-project.md).

## Read on

- The walkthrough: [Set up](../../handbook/17-walkthrough.md#172-set-up)
- The handbook: [Install](../../handbook/02-setup.md#22-install)
