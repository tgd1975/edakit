# Issue #801 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/issues/801), short as the rule for texts upstream asks.

### Title

```text
export: easyeda_export_pick_place returns xlsx when csv is asked
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.4.0 (code unchanged on 1.6.0), EasyEDA Pro 3.2.206, Linux.

`easyeda_export_pick_place` with `format: "csv"` writes an xlsx file named `….csv`. `exportPickPlace` ([export-operations.ts#L53](https://github.com/oaslananka/easyeda-mcp-pro/blob/e52d862bb7661bed6c760da6f3ed547b514aed27/easyeda-bridge-extension/src/export-operations.ts#L53)) calls `PCB_ManufactureData.getPickAndPlaceFile(projectId)`, but the signature is `getPickAndPlaceFile(fileName?, fileType?: 'xlsx' | 'csv', unit?)`: the project id becomes the file name, no `fileType` is passed, and EasyEDA falls back to xlsx.

**Expected:** `format` is passed as `fileType`, so `csv` gives CSV. (`txt` has no counterpart in the API.)

Workaround: we read the xlsx.
````
