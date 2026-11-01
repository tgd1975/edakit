patch
- The tests run in parallel (pytest-xdist in the group `dev`): `uv run --group dev pytest -q -n auto`. From the next version on, an update that moves only the dev tools is no version (`.github/versions.py`).
