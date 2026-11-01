# Pull request #799 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/799), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
feat(export): easyeda_export_odb through getOpenDatabaseDoublePlusFile
```

### Body

````markdown
## Summary

New tool `easyeda_export_odb` (profile `pro`) and bridge method `export.odb`. The extension calls `getOpenDatabaseDoublePlusFile(fileName, 'inch', {metallizedDrilledHoles, nonMetallizedDrilledHoles})`; the server writes the result as `<projectId>-odb.tgz` or `.zip` after checking the archive's magic bytes – anything else is refused and nothing is written. Tool counts, tool reference and capability tables updated.

Fixes #798

## Risk

Low – a new export tool, no design mutation. It adds one name to the method list in `src/bridge/types.ts` and the extension's `dispatcher.ts` (both critical paths), so the extension of the same version is needed. Revert to roll back.

## Validation

- Tests: the tool (tgz, zip, a non-archive, a failing bridge), the extension handler, the router's method list.
- On 1.6.0: `pnpm verify:fast` and the extension tests green; the full suite as on `main` (only the ngspice test fails here).
- Live: the same API call through a locally patched 1.4.0 server and extension on EasyEDA Pro 3.2.206; this branch itself not live yet.
````
