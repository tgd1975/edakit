# Issue – draft (M-10)

Not posted. Checked on 2026-11-01: easyeda-mcp-pro 1.6.0 is the newest release, the rebuild code unchanged on
`upstream/main` (`9601584`); no issue there covers it – #480 is the creation of copper zones, #596 the tool itself.
Found live on coin-cell-led the same day (GND poured on top and bottom), short as the rule for texts upstream asks.
Only a net's pours in one call – a refill of a filled pour is not edakit's case and stays out (the owner,
2026-11-01). The pull request goes with it ([pr-9-rebuild-copper.md](pr-9-rebuild-copper.md)).

### Title

```text
pcb: rebuild_copper can't verify a net's second pour in one call, then refuses every rebuild until EasyEDA restarts
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.6.0 (code unchanged on main 9601584), EasyEDA Pro 3.2.209, Linux.

Two fresh GND pours, top and bottom, created with `PCB_PrimitivePour.create`, then `easyeda_pcb_rebuild_copper {"net": "GND"}`: the first pour is `rebuilt`, the second `readback-mismatch` – EasyEDA's beta `rebuildCopperRegion` returns the first pour's Poured. `independentlyReconciled` would take that, but it wants exactly one new Poured for the whole batch and the returned pour to have had copper before the call ([L220-L232](https://github.com/oaslananka/easyeda-mcp-pro/blob/9601584fde2658a3452372d0faa9abcf42075180/easyeda-bridge-extension/src/pcb-mutation-operations.ts#L220-L232)).

From then on every rebuild throws "A previous native PCB copper rebuild ended without complete verification" ([L861](https://github.com/oaslananka/easyeda-mcp-pro/blob/9601584fde2658a3452372d0faa9abcf42075180/easyeda-bridge-extension/src/pcb-mutation-operations.ts#L861-L867)). A reconnect keeps the dispatcher, so only a restart of EasyEDA clears it.

**Expected:** a net's fresh pours verify in one call, as they do one call per pour.

**Workaround:** we rebuild one pour per call (`pourIds: [id]`).
````
