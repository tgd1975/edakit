# Issue #800 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/issues/800), short as the rule for texts upstream asks.

### Title

```text
api.call: DMT_Project.createProject returns ok: true with result null in the desktop client
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.4.0 (code unchanged on 1.6.0), EasyEDA Pro 3.2.206 desktop client with local projects, Linux.

`easyeda_api_call` with `DMT_Project.createProject("test")` returns `{ ok: true, result: null }` and creates nothing. EasyEDA's warn log says why: `/api/client/createProject … "msg":"请求参数path错误","detail":"path"` – the local server wants a folder path the extension API cannot pass. That part is EasyEDA's.

The server's part: `ok: true` reads as success. A client that goes on writes into whichever project is open – that happened to us.

**Expected:** a `create…` call that returns null or undefined comes back as an error, e.g. "not available in the desktop client – create the project in the GUI".
````
