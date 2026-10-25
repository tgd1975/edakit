**Title:** api.call: results are cut after 5 levels – make the depth configurable

**Environment:** easyeda-mcp-pro 1.4.0 (code unchanged on `main` at 1.5.4), EasyEDA Pro 3.2.206.

**What happens**

`easyeda_api_call` normalises every result with `normalizeValue(result, 5)` (`api-runtime.ts`, also
`system-api-operations.ts`). Deeper objects become `[MaxDepth]`. Several documented calls return their useful content
deeper than that:

- `PCB_Drc.check(true, false, true)` – the findings per category with `errData` (primitive ids, position,
  `minDistance`, layers) sit at level 6–8; with depth 5 only the categories are visible.
- `DMT_Project.getCurrentProjectInfo` – pages and title blocks of boards.
- the DRC rule configuration.

**Expected**

An optional `maxDepth` parameter on `easyeda_api_call` (default 5, upper limit e.g. 16), passed through to the
extension. The default keeps today's payload sizes; callers that need the detail ask for it.

**Proposed change** (branch `feat/api-call-max-depth` in the fork): schema field in the tool, `maxDepth` forwarded in
`api.call`, used by the extension's `apiCall`; tests for the default and for a deeper result.

**Our workaround:** a script that rewrites `normalizeValue(result, 5)` to 12 in the built extension bundle and
re-imports it – brittle across releases.
