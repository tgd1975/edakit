# PR – branch `fix/schematic-pdf-export`

### Title

```text
fix(export): schematic PDF through SCH_ManufactureData.getExportDocumentFile
```

### Description

```markdown
## Summary

`exportPdf` passed a schematic request to `callFirst` with `PCB_ManufactureData.getPdfFile` first in the list. That function always exists, so a schematic export called the PCB export with a params object it does not understand. For `what === 'schematic'` the extension now calls `SCH_ManufactureData.getExportDocumentFile(fileName?, 'PDF')`, which exports the active schematic as a vector PDF on EasyEDA Pro 3.2.206. Board and combined (`both`) requests are unchanged.

- New test: the schematic branch never reaches the PCB export and passes the optional file name.
- The existing test now covers `board` and `both`.

## Risk

- Risk level: low
- Affected areas: bridge extension (`export-operations.ts`)
- Rollback plan: revert the commit.

## Critical-path review

- [x] This PR does not touch a critical path listed in [Repository Governance](../docs/REPOSITORY_GOVERNANCE.md).
- [ ] This PR touches a critical path; CODEOWNERS and the affected risk area are identified below.

## External contributions

First contribution.

## Validation

- [ ] `pnpm verify` – ran `pnpm verify:fast` (green) and `pnpm test:extension` (all green)
- [x] Targeted tests added or updated (`easyeda-bridge-extension/tests/export-operations.test.ts`)
- [ ] Documentation updated when behavior or configuration changed (not needed)
- [ ] Manual or live EasyEDA validation completed when required (the same call has been used daily through a locally patched 1.4.0 extension on EasyEDA Pro 3.2.206)

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
