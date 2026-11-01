# Issue #794 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/issues/794), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
export: easyeda_export_pdf with scope "schematic" calls PCB_ManufactureData.getPdfFile
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.4.0 (code unchanged on 1.6.0), EasyEDA Pro 3.2.206, Linux.

`easyeda_export_pdf` with `scope: "schematic"` never exports the schematic. `exportPdf` ([export-operations.ts#L61](https://github.com/oaslananka/easyeda-mcp-pro/blob/e52d862bb7661bed6c760da6f3ed547b514aed27/easyeda-bridge-extension/src/export-operations.ts#L61)) hands both `PCB_ManufactureData.getPdfFile` and `SCH_ManufactureData.getExportDocumentFile` to `callFirst`, which takes the first function that exists – always the PCB one. Since #527 this fails cleanly as `not_available`, but the schematic still isn't exported.

**Expected:** for a schematic, call `SCH_ManufactureData.getExportDocumentFile(fileName?, 'PDF')`. On 3.2.206 it returns the active schematic as a vector PDF – we use it daily through a locally patched extension. Fix in #795.
````
