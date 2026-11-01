# PR – branch `feat/odb-export`

### Title

```text
feat(export): easyeda_export_odb through getOpenDatabaseDoublePlusFile
```

### Description

```markdown
## Summary

A new tool `easyeda_export_odb` exports the PCB as ODB++ (EasyEDA Pro's `getOpenDatabaseDoublePlusFile`, BETA in its
extension API), for assemblers that take ODB++ instead of Gerber. A new bridge method `export.odb` in the server's
method schema and in the extension's dispatcher; the extension calls the API in inch – its unit type admits
`ESYS_Unit.INCH` only – and returns the file through `normalizeBinaryResult`; the server writes it with
`writeExportPayload` once its magic bytes show a tgz or zip archive, named `<projectId>-odb.<tgz|zip>`.

- Input: `projectId`, `filePath?`, `platedHoles`, `nonPlatedHoles` (default `true`); profile `pro`, the declared tool
  counts of `pro`, `full`, `dev` and `experimental` one higher, the generated tool reference and capability tables.
- Tests: the tool with a mocked bridge (tgz and zip written, a non-archive refused with nothing written, a failing
  bridge), the extension handler (file name, inch, drill options; a missing projectId), the router's method list.
- `pnpm verify:fast` green; the whole suite green but for the test that expects no ngspice, as on `main`.

Fixes #<issue>

## Risk

- Risk level: low – a new tool, nothing existing changes but the method list (the registry hash with it): the
  extension of this version is needed, as for every release.
- Affected areas: server export tools, bridge method registry, extension export operations.
- Rollback plan: revert the commit.

## Critical-path review

- [x] This PR does not touch a critical path listed in [Repository Governance](../docs/REPOSITORY_GOVERNANCE.md).
- [ ] This PR touches a critical path; CODEOWNERS and the affected risk area are identified below.
```

Local stand-in until it is released: `edakit/easyeda/odb-tool-patch.mjs` (the tool, patched into the installed 1.4.0
by `mcp-server.sh`) and `bridge-extension-patch.sh` (the handler, through `board.exportGerbers` with `format: "odb"`).
Commit `8e3b1d9` on 1.6.0 (`e52d862`), not pushed yet.
