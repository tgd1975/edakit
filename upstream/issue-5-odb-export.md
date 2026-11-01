# Issue 5 – form "Feature Request"

### Title

```text
export: ODB++ export (PCB_ManufactureData.getOpenDatabaseDoublePlusFile) as a tool
```

**Affected Area:** `area:manufacturing-export`
**Impact / Priority:** `P2 - roadmap, docs, polish, or non-blocking issue`

### Problem

```markdown
Some assemblers do not take Gerber for assembly: AISLER assembles from ODB++ or native design files only. EasyEDA Pro
exports ODB++ itself (File > Export > ODB++, "ODB++ v8.0"), and its extension API has
`PCB_ManufactureData.getOpenDatabaseDoublePlusFile(fileName?, unit?, otherData?, layers?, objects?)` (BETA) → `File`,
with plated and non-plated drill holes, the drill table and the flying-probe file as `otherData`.

easyeda-mcp-pro has no tool for it, and no way around one: no export tool passes a parameter an extension could use for
ODB++, and `easyeda_api_call` returns its result through `normalizeValue`, which carries no file, while the export
tools return theirs through `normalizeBinaryResult` (base64).
```

### Proposed Solution

```markdown
A tool `easyeda_export_odb` beside `easyeda_export_gerbers`: input `projectId`, `filePath?`, `platedHoles`,
`nonPlatedHoles` (default `true`); a new bridge method `export.odb`, in which the extension calls
`PCB_ManufactureData.getOpenDatabaseDoublePlusFile(fileName, 'inch', otherData)` and returns the file through
`normalizeBinaryResult`; the server writes it with `writeExportPayload` once its magic bytes show a tgz or zip archive.
No `unit` input: the API's type admits `ESYS_Unit.INCH` only.
```

### Acceptance Criteria

```markdown
- [ ] `easyeda_export_odb` writes the ODB++ archive EasyEDA exports, named with its extension.
- [ ] A payload that is no archive is refused and nothing is written; an extension without the handler gives a clear
      error.
- [ ] Tests cover the tool and the extension handler (unit and the drill options passed through).
```

### Additional Context

```markdown
Found while adding AISLER as a maker in edakit (https://github.com/tgd1975/edakit, docs/concepts/done/ordering.md),
where a check holds the ODB++ to the released Gerber, drill and pick-and-place files. Tried on EasyEDA Pro 3.2.206
with a local stand-in of this tool: the archive holds `comp_+_top` and `comp_+_bot` with package, pins and the part
number, turns clockwise, and equals the export from File > Export > ODB++ but for the unit – the dialog writes mm,
the API inch. Without a file name EasyEDA names the archive `undefined`, so the tool passes one.
