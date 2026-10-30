# PR – branch `feat/odb-export` (not built yet)

### Title

```text
feat(export): easyeda_export_odb – ODB++ through PCB_ManufactureData.getOpenDatabaseDoublePlusFile
```

### Description

```markdown
## Summary

A new tool `easyeda_export_odb` exports the PCB as ODB++ (EasyEDA Pro's `getOpenDatabaseDoublePlusFile`, BETA in its
extension API), for assemblers that take ODB++ instead of Gerber. A new bridge method `board.exportOdb` in the server's
method registry and in the extension's dispatcher; the extension returns the file through `normalizeBinaryResult`,
the server writes it with `writeExportPayload` after checking that it is a zip or tgz archive.

- Input: `projectId`, `filePath?`, `unit` (`mm` | `inch`, default `mm`), `platedHoles`, `nonPlatedHoles`.
- Tests: the tool with a mocked bridge (archive written, a non-archive refused), the extension handler (arguments
  passed through).

Fixes #<issue>

## Risk

- Risk level: low – a new tool, nothing existing changes but the method registry (its hash with it).
- Affected areas: server export tools, bridge method registry, extension export operations.
- Rollback plan: revert the commit.

## Critical-path review

- [x] This PR does not touch a critical path listed in [Repository Governance](../docs/REPOSITORY_GOVERNANCE.md).
- [ ] This PR touches a critical path; CODEOWNERS and the affected risk area are identified below.
```

Local stand-in until it is released: `edakit/easyeda/odb-tool-patch.mjs` (the tool, patched into the installed 1.4.0
by `mcp-server.sh`) and `bridge-extension-patch.sh` (the handler, through `board.exportGerbers` with `format: "odb"`).
