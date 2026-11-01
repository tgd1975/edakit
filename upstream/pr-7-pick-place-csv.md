# Pull request #803 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/803) for #801, short as the rule for texts upstream asks; branch in the fork as named
in upstream/README.md.

### Title

```text
fix(export): pass the file type to getPickAndPlaceFile
```

### Body

````markdown
## Summary

`exportPickPlace` called `getPickAndPlaceFile(projectId)` without a file type, so EasyEDA wrote xlsx and the tool saved it as `.csv`. The extension now passes `'csv'` – both formats of the tool (csv, txt) are CSV text.

Fixes #801

## Risk

Low – one argument in `easyeda-bridge-extension/src/export-operations.ts`. Revert to roll back.

## Validation

- `export-operations.test.ts` and `dispatcher.test.ts` expect the type now; both fail without the fix.
- On 1.6.0: `pnpm verify:fast` and the extension tests green; the full suite as on `main` (only the ngspice test fails here).
- Not live yet: the signature is from the API types of EasyEDA Pro 3.2.206.
````
