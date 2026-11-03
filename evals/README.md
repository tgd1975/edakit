# Evals of the edakit plugin

Typical tasks on the reference circuits (`tests/reference.py`), run by `claude plugin eval` with a model of choice –
concept `docs/concepts/done/rules-at-scale.md`, section 8, and maker-coverage FT-24: edakit must work with Sonnet, not
only with the largest model.

| Case | Task | Graded by |
|---|---|---|
| `fault-motors`, `fault-audio`, `fault-cables` | find the fault built into a reference circuit with edakit | the `FAULT:` line names the place and the code; `edakit check` ran; no finding invented (judge) |
| `fault-guitar-sim` | the same, for a fault only the simulation shows | the line; `edakit sim` ran; no finding invented |
| `coverage` | what went unchecked for lack of data | the codes and the field named; `edakit check --coverage` ran |
| `add-led` | a status LED on GP8 from the block library, until check and sim are clean | the graph has it; block add, check and sim ran; the `DONE:` line |
| `requirements-inventory` | the inventory for the requirements file of led-bar with a two-line README (#97) | the README's eight LEDs and USB port are candidates; a candidate read from the circuit says inferred; the list "already checked by edakit"; no candidate edakit derived (judge) |
| `first-reader` | a reader new to edakit follows the start page and the quickstart to the first finding on the walkthrough's example, with only those pages | `edakit check` ran; PATH.reverse named; what it means and why it is accepted (judge) |
| `first-circuit` | a reader new to edakit makes a checked circuit of a one-line idea – a 9 V battery, a switch, two LEDs – with the site's Markdown as the only guide, no board (documentation-newcomer.md, N.5) | `edakit check` ran; a graph with two LEDs; the pages named as `site/…`; the `DONE:` line without an open error; a graph of its own with battery, switch and two LEDs, every acceptance with a reason (judge on the graph); the last check clean and the DONE line true to it (judge on the trace); at most six documentation pages opened with Read – a page read on from an offset not counted again –; no Read, Grep, Glob or Bash into edakit's code (`edakit/` of the plugin) |

Each case's `scaffold.sh` writes its project into the run's empty workspace with `tests/reference.py` (plain
`python3`, no edakit needed for that). The graders are regex and tool_used – free – and one judge per fault case and
for `requirements-inventory`.

## Running

```bash
git archive HEAD | tar -x -C /tmp/edakit-eval        # a copy without the .venv: uv's hard links are refused
cd /tmp/edakit-eval && UV_LINK_MODE=copy uv sync      # the copy's own environment, without hard links
claude plugin eval . --scaffold --allow-tools Bash Edit Write --trust-plugin --ablation none --runs 1 \
    --model claude-sonnet-5-5 --max-cost-usd 6 --no-publish
```

On Linux the sandbox of Bash needs `bubblewrap` and `socat`, and `TMPDIR` set to a directory outside `/tmp`,
`/var/tmp` and `/dev/shm` (`mkdir -p /srv/evaltmp`, owned by the user running it, `TMPDIR=/srv/evaltmp`): the harness
puts the run's workspace under `TMPDIR` and denies Bash writes to those three directories, and the denial is mounted
last – with the default `/tmp`, Bash cannot write the workspace (the Edit tool can), which is what the runs below and
the first two runs of `first-circuit` (TD-102) met. The plugin directory must contain no hard links – the harness
refuses case files reachable by another name, and uv fills a `.venv` with hard links from its cache –, hence the copy.
Run it as an ordinary user (`useradd -m eval`), not as root. A run has no network: `edakit part search`, `edakit stock`
and `edakit cost` cannot reach the shop, which the prompt of `first-circuit` says.

## Baseline, 2026-10-31

One run per case, judge Haiku, plugin at the commit after `Flyback finding names the part's kind`; in a cloud container
as root.

| Case | Sonnet 5.5 | Opus 5.5 |
|---|---|---|
| fault-motors | 1.00 | 1.00 |
| fault-audio | 1.00 | 1.00 |
| fault-cables | 1.00 | 1.00 |
| fault-guitar-sim | 1.00 | 1.00 |
| coverage | 1.00 | 1.00 |
| add-led | 0.40 | 1.00 |
| cost | 0.55 USD | 1.48 USD |

`add-led` with Sonnet: Bash could not write the workspace (`TMPDIR` under `/tmp`, see above); Sonnet stopped and asked
how to go on, Opus wrote the graph with the Edit tool. One run per case is a first reading, not a rate: repeat with
`--runs 3` before reading a difference into it.

What the first runs changed in edakit: `bin/edakit` falls back to the plugin's `.venv` where uv cannot write its cache;
`edakit sim` reports artifacts it could not write as a note after its complete results; the SessionStart hook names the
path of `bin/edakit` when edakit is not on PATH; the flyback finding names the motor's winding instead of a coil, which
a run had taken for a relay.
