# Pull request #805 – as posted (M-9)

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/805) for #804; branch in the fork as named in upstream/README.md.

### Title

```text
fix(schematic): apply mirror, addIntoBom and addIntoPcb after placement
```

### Body

````markdown
## Summary

`schematic.placeComponent` called `create(deviceItem, x, y)` and applied only `rotation` afterwards, so `mirror`, `addIntoBom` and `addIntoPcb` from `place_component` and `batch_write` were dropped. `applyPlacedRotation` becomes `applyPlacedState` and sets all four in the snapshot-merge `modify` it already made; a placement without them is not modified.

Fixes #804

## Risk

Low – `easyeda-bridge-extension/src/dispatcher.ts` only; `create()` keeps its three arguments. Revert to roll back.

## Validation

- Three tests in `dispatcher.test.ts`; two fail without the fix.
- On 1.6.0: `pnpm verify:fast` and the extension tests green.
- Live on EasyEDA Pro 3.2.209: the drop reproduced; the calls the fix makes – `create(deviceItem, x, y)`, then `modify` with the merged state – set all three. The rebuilt extension not run live.
````
