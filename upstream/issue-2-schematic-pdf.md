# Issue 2 – form "Bug Report"

### Title

```text
export: easyeda_export_pdf with scope "schematic" calls PCB_ManufactureData.getPdfFile
```

**Affected Area:** `area:manufacturing-export`
**Impact / Priority:** `P2 - roadmap, docs, polish, or non-blocking issue`

### Bug Description

```markdown
`exportPdf` in the bridge extension ([export-operations.ts#L61](https://github.com/oaslananka/easyeda-mcp-pro/blob/582f818bbb4c5ffd5ec707d0f600b6331822e8f2/easyeda-bridge-extension/src/export-operations.ts#L61)) does

    await callFirst(
      ['PCB_ManufactureData.getPdfFile', 'SCH_ManufactureData.getExportDocumentFile'],
      params.what === 'board' ? params : { ...params, type: 'schematic' },
    )

`callFirst` calls the first function that exists. `PCB_ManufactureData.getPdfFile` always exists, so a schematic request ends up in the PCB export with a params object it does not understand, and no schematic PDF comes back. #527 added payload validation, so this now fails cleanly – but the routing itself is unchanged.
```

### Steps to Reproduce

```markdown
1. Open a project with a schematic in EasyEDA Pro 3.2.206; make the schematic page active.
2. Call `easyeda_export_pdf` with `scope: "schematic"`.
3. The result is `exported: false` / not_available (since #527) or a PCB document – never the schematic.
```

### Acceptance Criteria

```markdown
- [ ] `scope: "schematic"` exports the active schematic as PDF.
- [ ] Tests cover the schematic and the board branch.
```

### Expected Behavior

```markdown
For a schematic the extension calls `SCH_ManufactureData.getExportDocumentFile(fileName?, 'PDF')`. On EasyEDA Pro 3.2.206 that returns the active schematic as a vector PDF – we have used it daily through a locally patched extension.
```

### Environment Info

```markdown
- easyeda-mcp-pro Version: 1.4.0 (observed); code path unchanged on main at 1.5.4 (582f818)
- Node.js Version: 24.14.1
- OS: Ubuntu (Linux 7.0)
- EasyEDA Pro Client: Desktop Client 3.2.206
- Bridge Extension Version: 1.4.0
- Tool Profile: full
```
