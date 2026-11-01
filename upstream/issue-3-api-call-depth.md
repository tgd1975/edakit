# Issue #796 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/issues/796), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
api.call: make the result depth of easyeda_api_call configurable (DRC details are cut at [MaxDepth])
```

### Body

````markdown
`easyeda_api_call` cuts every result at depth 5 (`normalizeValue(result, 5)`, [api-runtime.ts#L221](https://github.com/oaslananka/easyeda-mcp-pro/blob/e52d862bb7661bed6c760da6f3ed547b514aed27/easyeda-bridge-extension/src/api-runtime.ts#L221)); deeper levels come back as `[MaxDepth]`. Some documented calls carry their content deeper:

- `PCB_Drc.check(true, false, true)` – the details per finding (`errData`: primitive ids, position, `minDistance`) sit at levels 6–8.
- `PCB_Drc.getCurrentRuleConfiguration()` – the rule values sit 9 levels deep.

**Proposal:** an optional `maxDepth` (1–16, default 5) on `easyeda_api_call`, forwarded only when given, so existing payloads stay as they are. Today we patch the built extension to depth 12 after every release. Implementation in #797.
````
