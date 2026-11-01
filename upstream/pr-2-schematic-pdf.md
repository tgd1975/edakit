# Pull request #795 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/795), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
fix(export): schematic PDF through SCH_ManufactureData.getExportDocumentFile
```

### Body

````markdown
## Summary

For `what === 'schematic'` the extension now calls `SCH_ManufactureData.getExportDocumentFile(fileName?, 'PDF')` directly instead of going through `callFirst`, which always picked `PCB_ManufactureData.getPdfFile`. Board and `both` are unchanged.

Fixes #794

## Risk

Low – only `easyeda-bridge-extension/src/export-operations.ts`. Revert to roll back.

## Validation

- `export-operations.test.ts`: a new test for the schematic branch; the existing one covers board and both.
- On 1.6.0: `pnpm verify:fast` and the extension tests green; the full suite as on `main` (only the ngspice test fails here).
- Live: the same call used daily through a patched 1.4.0 extension on EasyEDA Pro 3.2.206.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
````
