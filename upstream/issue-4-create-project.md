**Title:** `DMT_Project.createProject` returns null in the local desktop client – report it as an error

**Environment:** EasyEDA Pro 3.2.206 desktop (local projects), easyeda-mcp-pro 1.4.0, Linux.

**What happens**

`easyeda_api_call` with `DMT_Project.createProject("name")` (also with `projectName`, a team path or a folder) returns
`{ ok: true, result: null }`. EasyEDA's own log shows why:

```text
[ERROR] [SERVER] json api /api/client/createProject" {"code":1111116,"msg":"请求参数path错误","detail":"path","httpCode":500}
```

The local server's `createProject` needs a folder `path`; the extension API passes `projectFriendlyName`,
`projectName`, `teamUuid`, `folderUuid`, … and none of them reaches `path`. So in the local desktop client a project
cannot be created through the API at all – this is EasyEDA's side, not the bridge's.

The problem for agents: `ok: true` with `result: null` looks like success. A client that goes on (opens the "new"
project, writes a schematic) writes into whatever project is open – it happened to us.

**Suggestion**

Where the bridge knows a call creates something (`DMT_Project.createProject`, maybe `DMT_*.create*` in general), turn a
null result into a typed error ("not available in the local desktop client – create the project in the GUI"), and
mention it in the tool description.
