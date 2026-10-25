**Title:** export: `easyeda_export_pdf` for a schematic calls `PCB_ManufactureData.getPdfFile`

**Environment:** easyeda-mcp-pro 1.4.0 (code unchanged on `main` at 1.5.4), EasyEDA Pro 3.2.206, Linux.

**What happens**

`exportPdf` in `easyeda-bridge-extension/src/export-operations.ts`:

```ts
await callFirst(
  ['PCB_ManufactureData.getPdfFile', 'SCH_ManufactureData.getExportDocumentFile'],
  params.what === 'board' ? params : { ...params, type: 'schematic' },
)
```

`callFirst` calls the first function that exists. `PCB_ManufactureData.getPdfFile` always exists, so the schematic
case calls the PCB export with a params object it does not understand – no schematic PDF (see also #527, closed with
payload validation; the routing itself is unchanged).

**Expected**

For a schematic: `SCH_ManufactureData.getExportDocumentFile(fileName?, 'PDF')`, which exports the active schematic as a
vector PDF on EasyEDA Pro 3.2.206 (signature read from the editor's API bundle; we use it daily through a patched
extension).

**Proposed fix** (branch `fix/schematic-pdf-export` in the fork): choose the function by `what`; tests for both
branches.
