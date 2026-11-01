#!/usr/bin/env bash
# Writes the project of this case into the run's empty workspace (tests/reference.py of the plugin): led-bar with a
# short README in the maker's words in place of the test project's – what the inventory must start from (#97).
set -euo pipefail
CASE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$CASE/../.." && pwd)"
python3 "$ROOT/tests/reference.py" . led-bar
cat > README.md <<'README'
# led-bar

Eight LEDs in a row, powered from a laptop's USB port. One button.
README
