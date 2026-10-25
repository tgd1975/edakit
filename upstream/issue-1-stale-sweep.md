# Issue 1 – form "Bug Report"

### Title

```text
bridge: stale sweep rejects requests before their own timeoutMs
```

**Affected Area:** `area:easyeda-bridge`
**Impact / Priority:** `P2 - roadmap, docs, polish, or non-blocking issue`

### Bug Description

```markdown
`BridgeManager.call(method, params, { timeoutMs })` accepts a per-request timeout, and the request's own `setTimeout` uses it ([manager.ts#L921](https://github.com/oaslananka/easyeda-mcp-pro/blob/582f818bbb4c5ffd5ec707d0f600b6331822e8f2/src/bridge/manager.ts#L921)). The stale sweep, however, compares every pending request with the global `BRIDGE_TIMEOUT_MS` ([manager.ts#L1158-L1175](https://github.com/oaslananka/easyeda-mcp-pro/blob/582f818bbb4c5ffd5ec707d0f600b6331822e8f2/src/bridge/manager.ts#L1158-L1175)):

    if (elapsed >= this.config.BRIDGE_TIMEOUT_MS) { … reject(new Error(`Bridge request "${entry.method}" expired (stale sweep)`)) }

So a request that was given more time than the default – a DRC or a copper-pour rebuild on a large board takes 30–120 s – is rejected by the sweep after 15–45 s although its own timeout has not run out. Requests a follower server relays to the leader are affected the same way, because the leader's sweep applies the leader's default.
```

### Steps to Reproduce

```markdown
1. Start the server with the default `BRIDGE_TIMEOUT_MS` (15000).
2. Issue a bridge call with a longer per-request timeout that runs longer than 45 s in EasyEDA, e.g. `manager.call('project.save', {}, { timeoutMs: 120000 })` against an extension that answers late (or a DRC of a ~120-part board in a throttled EasyEDA window).
3. The call fails after the next 30 s sweep tick with `Bridge request "…" expired (stale sweep)` instead of returning or timing out after 120 s.

A unit reproduction with fake timers is in the linked PR: it fails on `main` and passes with the fix.
```

### Acceptance Criteria

```markdown
- [ ] The stale sweep rejects a request only after that request's own timeout.
- [ ] A regression test covers a request whose `timeoutMs` exceeds `BRIDGE_TIMEOUT_MS`.
```

### Expected Behavior

```markdown
The sweep is defence in depth for leaked timers; it should use each entry's own timeout and never cut a request shorter than the caller asked for.
```

**Environment Info** – paste the output of `easyeda-mcp-pro --doctor`, or:

```markdown
- easyeda-mcp-pro Version: 1.4.0 (observed); code path unchanged on main at 1.5.4 (582f818)
- Node.js Version: 24.14.1 (observed), 24.22.1 (tests)
- pnpm Version: 11.28.8 (tests)
- OS: Ubuntu (Linux 7.0)
- EasyEDA Pro Client: Desktop Client 3.2.206
- Bridge Extension Version: 1.4.0 (locally patched result depth)
- Tool Profile: full
```

**Relevant Log Output:** leave empty, or:

```shell
Bridge request "drc.run" expired (stale sweep)
```

**Workaround (add at the end of the description if you like):** `BRIDGE_TIMEOUT_MS=120000` for every server instance that may hold the bridge port.
