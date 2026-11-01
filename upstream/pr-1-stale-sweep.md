# Pull request #793 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/793), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
fix(bridge): stale sweep honours each request's own timeout
```

### Body

````markdown
## Summary

The stale sweep rejected pending requests after the global `BRIDGE_TIMEOUT_MS`, even when the caller had passed a longer `timeoutMs`. Each pending request now keeps its own timeout, and the sweep compares against that.

Fixes #792

## Risk

Low. Only `src/bridge/manager.ts` (a critical path): the expiry condition of pending requests – no change to auth, permissions or writes. Revert to roll back.

## Validation

- Regression test in `tests/unit/bridge/manager.test.ts` (fake timers): fails on `main`, passes with the fix.
- On 1.6.0: `pnpm verify:fast` green; the full suite green except `workflows.test.ts` (power rail), which fails on `main` here too because ngspice is installed.
- Live: seen on 1.4.0 with long DRC runs, worked around with `BRIDGE_TIMEOUT_MS=120000`.
````
