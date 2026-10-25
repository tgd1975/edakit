# PR – branch `feat/api-call-max-depth`

### Title

```text
feat(api): optional maxDepth for easyeda_api_call results
```

### Description

```markdown
## Summary

`easyeda_api_call` normalised every result to depth 5, so deeper content came back as `[MaxDepth]` – e.g. the per-finding details of `PCB_Drc.check(true, false, true)` or the DRC rule configuration.

- Tool schema: optional `maxDepth` (integer 1–16), described in the schema.
- Server: forwards `maxDepth` in `api.call` only when it is given – existing callers and payloads are unchanged.
- Extension: `callAllowedApi(path, args, maxDepth = 5)` normalises to the requested depth, clamped to 1–16 (`clampApiResultDepth`).
- Tests: server forwarding (with and without `maxDepth`), extension forwarding, default cut vs. deeper result, clamping.

## Risk

- Risk level: low
- Affected areas: server (`src/tools/L0_diagnostics_api.ts`), bridge extension (`api-runtime.ts`, `system-api-operations.ts`)
- Rollback plan: revert the commit; the parameter is optional and defaults to today's depth.

## Critical-path review

- [x] This PR does not touch a critical path listed in [Repository Governance](../docs/REPOSITORY_GOVERNANCE.md).
- [ ] This PR touches a critical path; CODEOWNERS and the affected risk area are identified below.
- Author self-review evidence: `easyeda_api_call` is a high-risk tool, but this changes only the depth of the returned result – no change to the allowlist, to `confirmWrite` or to what is executed. The upper limit (16) bounds the payload; the transport's payload-size checks still apply.

## External contributions

First contribution.

## Validation

- [ ] `pnpm verify` – ran `pnpm verify:fast` (green), `pnpm test:extension` (all green) and `pnpm test` (two failures that also occur on unchanged `main` here or pass alone, see the other PRs)
- [x] Targeted tests added or updated
- [ ] Documentation updated when behavior or configuration changed (the schema description documents the parameter)
- [ ] Manual or live EasyEDA validation completed when required (depth 12 used daily through a locally patched 1.4.0 extension)

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
