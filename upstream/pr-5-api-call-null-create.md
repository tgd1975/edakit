# Pull request #802 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/802) for #800, short as the rule for texts upstream asks; branch in the fork as named
in upstream/README.md.

### Title

```text
fix(api): report an empty create result of easyeda_api_call as a failure
```

### Body

````markdown
## Summary

A `create…` call that answers null or undefined created nothing – e.g. `DMT_Project.createProject` in the desktop client. `easyeda_api_call` returned `ok: true` for it; now it returns `ok: false` with an error. Other null results (getters) are unchanged.

Fixes #800

## Risk

Low – only the result handling of `easyeda_api_call` in `src/tools/L0_diagnostics_api.ts`. A caller that relied on `ok: true` with `null` from a create method now sees the failure. Revert to roll back.

## Validation

- New test in `tests/unit/tools/registry.test.ts`: fails without the fix, passes with it; a getter's null and a real create result stay `ok: true`.
- On 1.6.0: `pnpm verify:fast` green; the full suite as on `main` (only the ngspice test fails here).
````
