**Title:** bridge: stale sweep rejects requests before their own `timeoutMs`

**Environment:** easyeda-mcp-pro 1.4.0 (code unchanged on `main` at 1.5.4), EasyEDA Pro 3.2.206, Linux.

**What happens**

`BridgeManager.call(method, params, { timeoutMs })` accepts a per-request timeout, and the request's own `setTimeout`
uses it. The stale sweep (`startStaleSweep`, every 30 s) however compares every pending request with the global
`BRIDGE_TIMEOUT_MS`:

```ts
if (elapsed >= this.config.BRIDGE_TIMEOUT_MS) { … entry.reject(new Error(`Bridge request "${entry.method}" expired (stale sweep)`)) }
```

So a request that was given more time than the default – a DRC or a copper-pour rebuild on a large board takes
30–120 s – is rejected by the sweep after 15 s to 45 s, although its own timeout has not expired. The same happens to
requests a follower server relays to the leader: the leader's sweep applies the leader's default.

**Reproduce**

Default `BRIDGE_TIMEOUT_MS` (15000). Call a tool that passes a longer `timeoutMs` and runs longer than 45 s in
EasyEDA (e.g. DRC of a ~120-part board in a throttled window). The call fails with `expired (stale sweep)` instead of
returning or timing out after its own limit.

**Expected**

The sweep uses each entry's own timeout (it is meant as defence in depth for leaked timers, not as a second, shorter
limit).

**Proposed fix** (branch `fix/stale-sweep-per-request-timeout` in the fork): store `timeoutMs` in the request entry
and compare `elapsed >= entry.timeoutMs` in the sweep; regression test with a request whose `timeoutMs` exceeds the
default.

**Our workaround:** `BRIDGE_TIMEOUT_MS=120000` for every server instance that may hold the bridge port.
