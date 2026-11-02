#!/usr/bin/env bash
# The first reader of docs/concepts/done/documentation.md ("Measures"): the start page, the entry pages and the example
# of the walkthrough copied into the run's empty workspace – the site as the only input.
set -euo pipefail
CASE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$CASE/../.." && pwd)"
cp "$ROOT/README.md" .
mkdir -p docs examples
cp "$ROOT/docs/quickstart.md" "$ROOT/docs/how-it-works.md" "$ROOT/docs/glossary.md" docs/
cp -r "$ROOT/examples/coin-cell-led" examples/
rm -rf examples/coin-cell-led/build
