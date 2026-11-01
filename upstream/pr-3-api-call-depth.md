# Pull request #797 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/797), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
feat(api): optional maxDepth for easyeda_api_call results
```

### Body

````markdown
## Summary

`easyeda_api_call` takes an optional `maxDepth` (integer 1–16). The server forwards it in `api.call` only when given; the extension normalises the result to that depth (clamped). Without it nothing changes (depth 5).

Fixes #796

## Risk

Low – only the depth of the returned result; the allowlist, `confirmWrite` and what runs are untouched, and the upper bound keeps payloads limited. Revert to roll back.

## Validation

- Tests for the server forwarding (with and without `maxDepth`) and the extension's depth and clamping.
- On 1.6.0: `pnpm verify:fast` and the extension tests green; the full suite as on `main` (only the ngspice test fails here).
- Live: depth 12 used daily through a patched 1.4.0 extension.
````
