# Dry run: the bell's T-Display as footprint data

The dry run of step 3.6 of the [implementation plan](../../implementation-plan.md), written on 2026-10-29 and kept
here for its live run. Both scripts work on a scratch copy of the Christmas bell (`edakit.toml` and `hardware/` of the
main project and of `variants/esp32`), never on the bell itself:

```bash
python3 tdisplay_data.py <copy>/variants/esp32/hardware/parts/C18722937.json
uv run python compare_build.py <copy>/variants/esp32 <bell>/variants/esp32/hardware/lib/tdisplay_device.py
```

- `tdisplay_data.py` writes `footprint_data` into the copy's parts entry of the T-Display: the pads, lines, texts and
  outline as `tdisplay_device.py` builds them, and the symbol as a box. Step 1 of the live run starts from this entry.
- `compare_build.py` compares the calls `edakit part build` would make with the script's own (pads, polylines, texts,
  the symbol box), the data's box with the bell's dump, runs P-10 on the dump and prints the hashes. It loads the
  script for its pure functions; nothing of EasyEDA is called.

The result on the bell at `f56b463`:
- the pads lie within 0.000 mil of the script's;
- P-10 finds no difference against the dump (0.0013 mm);
- the symbol box is 60 wide, the script's 120.

They are scripts, not pytest tests, and edakit's pytest does not collect them.
