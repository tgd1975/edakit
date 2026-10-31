#!/usr/bin/env bash
# Writes the project of this case into the run's empty workspace (tests/reference.py of the plugin).
set -euo pipefail
CASE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$CASE/../.." && pwd)"
python3 "$ROOT/tests/reference.py" . guitar "a reference above the inputs' range"
