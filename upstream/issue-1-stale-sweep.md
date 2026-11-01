# Issue #792 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/issues/792), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
bridge: stale sweep rejects requests before their own timeoutMs
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.4.0 (code unchanged on 1.6.0), EasyEDA Pro 3.2.206, Linux.

The stale sweep compares every pending request with the global `BRIDGE_TIMEOUT_MS` ([manager.ts#L1158-L1175](https://github.com/oaslananka/easyeda-mcp-pro/blob/e52d862bb7661bed6c760da6f3ed547b514aed27/src/bridge/manager.ts#L1158-L1175)), not with the request's own `timeoutMs`. A call given more time – a DRC on a large board with `timeoutMs: 120000` – fails after 15–45 s with `Bridge request "drc.run" expired (stale sweep)` although its own timer has not run out.

**Expected:** the sweep uses each request's own timeout.

Workaround: `BRIDGE_TIMEOUT_MS=120000` on every server instance. Fix with a regression test in #793.
````
