patch
- An `easyeda` script that calls `eda.ensure_pcb_focus`, `activate_pcb` or `save_pcb` before `eda.open_pcb` is told to open the board's PCB first, not left with `KeyError: 'uuid'`; handbook 8.6 names the order (#339).
