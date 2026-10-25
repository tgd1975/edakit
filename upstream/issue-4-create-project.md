# Issue 4 – form "Bug Report"

### Title

```text
api.call: DMT_Project.createProject returns ok/null in the local desktop client – report it as an error
```

**Affected Area:** `area:easyeda-bridge`
**Impact / Priority:** `P2 - roadmap, docs, polish, or non-blocking issue`

### Bug Description

```markdown
In the local desktop client, `easyeda_api_call` with `DMT_Project.createProject("name")` – also with `projectName`, a team path or a folder – returns `{ ok: true, result: null }` and creates nothing. EasyEDA's own log (`~/Documents/EasyEDA-Pro/logs/warn/<date>.log`) shows why:

    [ERROR] [SERVER] json api /api/client/createProject" {"code":1111116,"msg":"请求参数path错误","detail":"path","httpCode":500}

The local server's `createProject` needs a folder `path`; the extension API passes `projectFriendlyName`, `projectName`, `teamUuid`, `folderUuid`, … and none of them reaches `path`. So in the local client a project cannot be created through the API at all – that part is EasyEDA's.

The bridge's part: `ok: true` with `result: null` reads as success. A client that goes on – opens the "new" project, writes a schematic – writes into whatever project is open. That happened to us.
```

### Steps to Reproduce

```markdown
1. EasyEDA Pro desktop 3.2.206 with a local project open.
2. `easyeda_api_call` `{ path: "DMT_Project.createProject", args: ["test"], confirmWrite: true }`.
3. Result `{ ok: true, result: null }`; no project file appears; EasyEDA's warn log contains the error above.
```

### Acceptance Criteria

```markdown
- [ ] A create call that returns null/undefined is reported as a typed error (e.g. not_available: "creating projects is not available in the local desktop client – create the project in the GUI"), not as `ok: true`.
- [ ] The tool description mentions the limitation.
```

### Expected Behavior

```markdown
Either a created project UUID or an explicit error.
```

### Environment Info

```markdown
- easyeda-mcp-pro Version: 1.4.0
- Node.js Version: 24.14.1
- OS: Ubuntu (Linux 7.0)
- EasyEDA Pro Client: Desktop Client 3.2.206, local projects
- Bridge Extension Version: 1.4.0
- Tool Profile: full
```
