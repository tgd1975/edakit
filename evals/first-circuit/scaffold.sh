#!/usr/bin/env bash
# The newcomer's test of docs/concepts/new/documentation-newcomer.md (step N.5): the site's Markdown – the start page,
# docs/ without the concepts, the handbook and the walkthrough's example – under site/, and an empty git repository
# beside it for the project of a one-line idea.
set -euo pipefail
CASE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$CASE/../.." && pwd)"
mkdir -p site/docs site/examples
cp "$ROOT/README.md" site/
cp -r "$ROOT/handbook" site/
(cd "$ROOT/docs" && find . -name '*.md' -not -path './concepts/*' -not -path './catalog/*' -print0) |
    while IFS= read -r -d '' f; do mkdir -p "site/docs/$(dirname "$f")"; cp "$ROOT/docs/$f" "site/docs/$f"; done
cp -r "$ROOT/examples/coin-cell-led" site/examples/
rm -rf site/examples/coin-cell-led/build
git init -q .
