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
A tool `easyeda_export_odb` beside `easyeda_export_gerbers`: input `projectId`, `filePath?`, `unit` (`mm` | `inch`,
default `mm`), `platedHoles`, `nonPlatedHoles` (default `true`); the extension calls
`PCB_ManufactureData.getOpenDatabaseDoublePlusFile(fileName, unit, otherData)` and returns the file through
`normalizeBinaryResult`; the server writes it with `writeExportPayload` and checks that it is a zip or tgz archive.

A new bridge method (`board.exportOdb`) is the clean way; the method registry and its hash change with it. As a local
workaround, edakit routes the call through `board.exportGerbers` with `format: "odb"`, so that the pinned 1.4.0 keeps
its registry, and marks the answer `format: "odb"` so that an extension without the handler is recognised – not a
proposal for upstream.
```

### Acceptance Criteria

```markdown
- [ ] `easyeda_export_odb` writes the ODB++ archive EasyEDA exports, in mm by default.
- [ ] An extension without the handler gives a clear error, never a Gerber ZIP.
- [ ] Tests cover the tool and the extension handler (unit and the drill options passed through).
```

### Additional Context

```markdown
Found while adding AISLER as a maker in edakit (https://github.com/tgd1975/edakit, docs/concepts/done/ordering.md),
where a check holds the ODB++ to the released Gerber, drill and pick-and-place files. Not yet tried against EasyEDA:
whether the export holds the component layers (packages, pins, part numbers) and its rotation convention are open.
