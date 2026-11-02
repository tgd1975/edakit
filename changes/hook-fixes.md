patch
- The pre-commit hook's edakit block holds under the project's `set -euo pipefail`: without edakit on the PATH it still reaches the plugin, and a failing step still blocks with its exit code. A block of 1.0.11 counts as older; the session start names it, `edakit hook install` renews it.
- `edakit hook run` takes the file of `doc_pin_table` as one of the configuration's inputs – under `locks` or `checks`, also in a JSON graph wrapped in `graph` – so a change to the documented pin table runs `edakit check` (pytree's `docs/hardware.md`).
