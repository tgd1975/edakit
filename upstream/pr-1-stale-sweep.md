# PR – branch `fix/stale-sweep-per-request-timeout`

### Title

```text
fix(bridge): stale sweep honours each request's own timeout
```

### Description

```markdown
## Summary

The stale sweep compared every pending request with the global `BRIDGE_TIMEOUT_MS`. A request that was given a longer `timeoutMs` (a DRC or a copper rebuild on a large board) was rejected with `expired (stale sweep)` after 15–45 s although its own timer had not run out. The sweep is defence in depth for leaked timers, so it now uses the timeout stored with each request.

- `PendingRequest` carries `timeoutMs`; `call()` stores it; the sweep compares `elapsed >= entry.timeoutMs`.
- Regression test with fake timers: a request with `timeoutMs: 120000` survives two sweeps past the 15 s default and ends after its own 120 s. It fails on `main` and passes with the fix.

## Risk

- Risk level: low
- Affected areas: server (`src/bridge/manager.ts`)
- Rollback plan: revert the commit; behaviour returns to the global sweep limit.

## Critical-path review

- [ ] This PR does not touch a critical path listed in [Repository Governance](../docs/REPOSITORY_GOVERNANCE.md).
- [x] This PR touches a critical path; CODEOWNERS and the affected risk area are identified below.
- Critical paths and owners: `src/bridge/manager.ts` (Remote transport and bridge) – @oaslananka
- Independent human reviewer: maintainer
- Author self-review evidence: no change to permissions, secrets, authentication or mutation boundaries; only the expiry condition of already pending requests. A request can now live up to its own `timeoutMs` (bounded by the callers, max. 120 s in `EnvSchema`) instead of being cut at the default.

## External contributions

First contribution.

## Validation

- [ ] `pnpm verify` – ran `pnpm verify:fast` (green) and `pnpm test`; two failures there also occur on unchanged `main` in this environment (`workflows.test.ts` power rail: ngspice is installed here) or pass when run alone (`lint-surface-policy.test.ts`, timing under load)
- [x] Targeted tests added or updated (`tests/unit/bridge/manager.test.ts`)
- [ ] Documentation updated when behavior or configuration changed (not needed)
- [ ] Manual or live EasyEDA validation completed when required (seen live on 1.4.0 with long DRC runs; worked around with `BRIDGE_TIMEOUT_MS=120000`)

## Security and supply chain

- [x] No secrets, credentials, private design data, or generated reports are committed
- [x] New dependencies are justified and exact-pinned where appropriate (none added)
- [x] GitHub Actions remain pinned to full commit SHAs (no workflow changes)
- [x] Permissions, fork behavior, and untrusted inputs were reviewed for workflow changes (no workflow changes)
- [x] Breaking changes and release impact are documented (none)

## Automated review disposition

- [ ] Every inline human, bot, and agent review thread is resolved.
- [ ] Top-level bot and agent comments were inspected even when their checks passed.
- [ ] Valid findings were fixed and false positives or accepted risks have an explicit rationale.

| Source | Finding or comment URL | Resolution or disposition evidence |
| ------ | ---------------------- | ---------------------------------- |
|        |                        |                                    |

## Emergency exception evidence

- [x] Not applicable; normal governance controls were used.

## Related work

Closes #<issue number>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
