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

Each case's `scaffold.sh` writes its project into the run's empty workspace with `tests/reference.py` (plain
`python3`, no edakit needed for that). The graders are regex and tool_used – free – and one judge per fault case.

## Running

```bash
git archive HEAD | tar -x -C /tmp/edakit-eval        # a copy without the .venv: uv's hard links are refused
cd /tmp/edakit-eval && UV_LINK_MODE=copy uv sync      # the copy's own environment, without hard links
claude plugin eval . --scaffold --allow-tools Bash Edit Write --trust-plugin --ablation none --runs 1 \
    --model claude-sonnet-5-5 --max-cost-usd 6 --no-publish
```

On Linux the sandbox of Bash needs `bubblewrap` and `socat`. The plugin directory must contain no hard links – the
harness refuses case files reachable by another name, and uv fills a `.venv` with hard links from its cache –, hence
the copy. Run it as an ordinary user: as root the harness cannot seal the workspace, and in the runs below Bash could
not write the workspace (the Edit tool could).

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

`add-led` with Sonnet: Bash could not write the workspace (root, see above); Sonnet stopped and asked how to go on,
Opus wrote the graph with the Edit tool. One run per case is a first reading, not a rate: repeat with `--runs 3` before
reading a difference into it.

What the first runs changed in edakit: `bin/edakit` falls back to the plugin's `.venv` where uv cannot write its cache;
`edakit sim` reports artifacts it could not write as a note after its complete results; the SessionStart hook names the
path of `bin/edakit` when edakit is not on PATH; the flyback finding names the motor's winding instead of a coil, which
a run had taken for a relay.
