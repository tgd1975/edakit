# Issue #804 – as posted (M-9)

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/issues/804) after the live reproduction the same day, short as the rule for texts
upstream asks.

### Title

```text
schematic: place_component and batch_write drop mirror, addIntoBom and addIntoPcb
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.4.0 (bridge code unchanged on 1.6.0), EasyEDA Pro 3.2.209, Linux.

`easyeda_schematic_batch_write` with a component create `{"mirror": true, "addIntoBom": false, "addIntoPcb": false}` reports `applied`, but `SCH_PrimitiveComponent.get` reads `Mirror: false`, `AddIntoBom: true`, `AddIntoPcb: true`. `easyeda_schematic_place_component` takes the same fields. Both send them to `schematic.placeComponent`, which calls `SCH_PrimitiveComponent.create(deviceItem, x, y)` only ([dispatcher.ts#L1494](https://github.com/oaslananka/easyeda-mcp-pro/blob/e52d862bb7661bed6c760da6f3ed547b514aed27/easyeda-bridge-extension/src/dispatcher.ts#L1494-L1499)) and applies just `rotation` afterwards.

**Expected:** the three fields take effect, as `rotation` does. A `SCH_PrimitiveComponent.modify` with them after the create sets all three on 3.2.209.

Workaround: we place the part, then call `SCH_PrimitiveComponent.modify(id, { addIntoBom: false })`.
````
