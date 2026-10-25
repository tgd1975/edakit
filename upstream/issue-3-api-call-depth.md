# Issue 3 – form "Feature Request"

### Title

```text
api.call: make the result depth of easyeda_api_call configurable (DRC details are cut at [MaxDepth])
```

**Area:** `area:easyeda-bridge`
**Risk Class:** `No special risk`

### Problem Statement

```markdown
`easyeda_api_call` normalises every result with `normalizeValue(result, 5)` ([api-runtime.ts#L221](https://github.com/oaslananka/easyeda-mcp-pro/blob/582f818bbb4c5ffd5ec707d0f600b6331822e8f2/easyeda-bridge-extension/src/api-runtime.ts#L221)). Deeper levels come back as `[MaxDepth]`. Several documented calls carry their useful content deeper than that:

- `PCB_Drc.check(true, false, true)`: the findings per category with `errData` (primitive ids, position, `minDistance`, layers) sit at level 6–8 – with depth 5 only the category names are visible.
- `PCB_Drc.getCurrentRuleConfiguration`: the rule values.
- `DMT_Project.getCurrentProjectInfo`: pages and title blocks of boards.
```

### Proposed Solution

```markdown
An optional `maxDepth` on `easyeda_api_call` (integer 1–16, default 5 as today). The server forwards it in `api.call` only when given; the extension's `callAllowedApi` normalises to it. Callers that need the detail ask for it, payload sizes stay unchanged otherwise.
```

### Alternatives Considered

```markdown
We patch the built extension bundle (`normalizeValue(result, 5)` → 12) and re-import it after every release – brittle, and every user needs a modified extension. A fixed higher default would grow every payload.
```

### Acceptance Criteria

```markdown
- [ ] `maxDepth` in the tool schema, validated (1–16), documented in the description.
- [ ] Default behaviour unchanged when it is omitted.
- [ ] Tests: forwarding by the server, depth handling and clamping in the extension.
```

### Additional Context

```markdown
Implementation with tests in the linked PR.
```
