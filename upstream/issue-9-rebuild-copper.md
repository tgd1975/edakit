# Issue – draft (M-10)

Not posted. Checked on 2026-11-01: easyeda-mcp-pro 1.6.0 is the newest release, the rebuild code unchanged on
`upstream/main` (`9601584`); no issue there covers it – #480 is the creation of copper zones, #596 the tool itself.
Found live on coin-cell-led the same day (GND poured on top and bottom), short as the rule for texts upstream asks.

### Title

```text
pcb: rebuild_copper can't verify a net's second pour or a refill, then refuses every rebuild until EasyEDA restarts
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.6.0 (code unchanged on main 9601584), EasyEDA Pro 3.2.209, Linux.

Two GND pours, top and bottom, created with `PCB_PrimitivePour.create`:

- `easyeda_pcb_rebuild_copper {"net": "GND"}`: the first pour is `rebuilt`, the second `readback-mismatch` (rebuild source mismatch) – EasyEDA's beta `rebuildCopperRegion` returns the net's first pour. `independentlyReconciled` would take that, but it expects exactly one new Poured for the whole batch ([L225](https://github.com/oaslananka/easyeda-mcp-pro/blob/9601584fde2658a3452372d0faa9abcf42075180/easyeda-bridge-extension/src/pcb-mutation-operations.ts#L220-L226)).
- A second rebuild of a pour that already has copper ends `readback-mismatch` too; a pour poured before the call is never reconciled (L220).

After either, every rebuild throws "A previous native PCB copper rebuild ended without complete verification" ([L861](https://github.com/oaslananka/easyeda-mcp-pro/blob/9601584fde2658a3452372d0faa9abcf42075180/easyeda-bridge-extension/src/pcb-mutation-operations.ts#L861-L867)). A reconnect keeps the dispatcher, so only a restart of EasyEDA clears it.

**Expected:** a net's fresh pours verify in one call; a refill verifies or fails without the lock – or the lock can be cleared once the PCB has been checked.

**Workaround:** we create the pours anew before each fill and rebuild one pour per call (`pourIds: [id]`), which verifies.
````
