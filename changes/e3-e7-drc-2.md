patch
- The DRC of `route all`, `silk apply` and the gate runs at once and reloads the PCB only when it reports Connection Errors, then runs once more (E-7) – `route all` no longer reloads before it unless `[routing] drc_rules = "write"`; the PCB tab's probe throwing on 3.2.209 counts as an inactive tab (E-3).
