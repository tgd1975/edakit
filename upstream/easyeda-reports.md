# EasyEDA Pro – the reports as posted

Posted at [easyeda/easyeda-api-sdk](https://github.com/easyeda/easyeda-api-sdk/issues) on 2026-11-01 on the
owner's word, under the account tgd1975, after the live check on EasyEDA Pro 3.2.209 and the check of every call
against the JSDoc of the client's types ([README.md](README.md), "How EasyEDA takes reports"). What became of each
requirement is in the tables there. A draft not posted yet says so in its heading.

## E-1 – [#45](https://github.com/easyeda/easyeda-api-sdk/issues/45)

### Title

```text
V3.2.209: dmt_Project.createProject returns undefined in the desktop client – `path` never reaches the local server
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client with local projects (pro-api 0.3.59).

```js
await eda.dmt_Project.createProject('probe');
// undefined; the client's log:
// /api/client/createProject {"code":1111116,"msg":"请求参数path错误","detail":"path"}

const teams = await eda.dmt_Team.getAllTeamsInfo();   // the project folders, uuid = folder path
await eda.dmt_Project.createProject('probe', 'probe', teams[0].uuid);
// undefined, nothing in the log
```

The API's createProject builds its request with `path: undefined`; the local server needs the folder.

**Expected:** the project is created in the team's folder (or the default one), as *File → New → Project* does.

**Workaround:** we create each project by hand.
````

## E-2 – [#46](https://github.com/easyeda/easyeda-api-sdk/issues/46)

### Title

```text
V3.2.209: pcb_Document.importChanges(uuid, true) ignores `force` – opens the dialog, returns true, imports nothing
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client (pro-api 0.3.59).

A part placed in the schematic, saved; PCB of the same board active:

```js
await eda.pcb_Document.importChanges(schematicUuid, true);
// true – but "Confirm Importing changes information" opens and nothing is imported until it is confirmed
```

The handler behind it reads only `source` (`importChanges(e){let{source:i}=e||{}; …}`); `uuid` and `force` are dropped.

**Expected:** as documented – `force=true` imports without the dialog and returns when done.

**Workaround:** we create PCB parts with `pcb_PrimitiveComponent.create`/`modify`.
````

## E-4 – [#47](https://github.com/easyeda/easyeda-api-sdk/issues/47)

### Title

```text
Feature request: install or update an extension without the GUI
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client.

Installing or updating an extension takes four GUI steps: uninstall the old one, import the `.eext`, allow "External interaction", restart. Your run-api-gateway (easyeda-api-skill) needs them too, and so does every update of a bridge extension.

There is no command-line option, no folder the client reads and no API call for it.

**Wish:** one of
- `easyeda-pro --install-extension x.eext`
- a folder whose `.eext` files the client installs at start
- an API call for extension management

with "External interaction" settable the same way.
````

## E-5 – comment on [#36](https://github.com/easyeda/easyeda-api-sdk/issues/36)

````markdown
Same on 3.2.209 (Linux desktop client) – and `modify` is lost the same way:

```js
const a = await eda.sch_PrimitiveText.create(300, 300, 'A');
const b = await eda.sch_PrimitiveText.create(300, 350, 'B');
await eda.sch_Document.save();
await eda.sch_PrimitiveText.delete(a.primitiveId);                    // true
await eda.sch_PrimitiveText.modify(b.primitiveId, { content: 'C', x: 400 });
await eda.sch_Document.save();                                        // true
// close the page, open it again:
await eda.sch_PrimitiveText.get([a.primitiveId, b.primitiveId]);
// both back as before: 'A' at 300/300, 'B' at 300/350
```

What works for us: `eda.sch_PrimitiveCircle.delete(textId)` deletes the text, and that deletion is saved.
````

## E-6 – comment on [#38](https://github.com/easyeda/easyeda-api-sdk/issues/38)

````markdown
Same on 3.2.209 (Linux desktop client, local project), on a routed two-layer board with about 190 track segments and 26 vias, PCB tab active:

```js
await eda.pcb_Document.clearRouting('all');
// no answer after 120 s, no dialog; every track and via is still there
```

We delete them by id instead (`pcb_PrimitiveLine.delete`, `pcb_PrimitiveVia.delete`).
````

## E-9 – [#48](https://github.com/easyeda/easyeda-api-sdk/issues/48)

### Title

```text
Feature request: dmt_Project.modifyProjectFriendlyName and modifyProjectDescription
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client, local projects.

Both are `@internal` ("已挂起 (2024/01/03)：编辑器暂无接口可实现") and return `false`. A script that sets up projects can therefore neither rename one nor set its description – only the GUI can.

**Wish:** both work, for local and online projects.
````

## E-11 – [#49](https://github.com/easyeda/easyeda-api-sdk/issues/49)

### Title

```text
Feature request: update placed parts to their edited footprint through the API
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client.

After a footprint of the project library is edited (`lib_Footprint.openInEditor`, pads changed, saved), the placed parts keep their old copy. `pcb_PrimitiveComponent.modify` has no footprint property and no call updates them, so we delete the parts and place them again.

**Wish:** a call that updates placed parts (all, or by id) to the current footprint, keeping position, rotation, layer and nets.
````

## E-12 – [#50](https://github.com/easyeda/easyeda-api-sdk/issues/50)

### Title

```text
V3.2.209: lib_Footprint.getDocumentSource never answers in the desktop client
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client (pro-api 0.3.59).

```js
await eda.lib_Footprint.getDocumentSource('ccc4e0b0d3734ba393745f2774fd8d65');   // system library
await eda.lib_Footprint.getDocumentSource(footprintUuid, projectLibraryUuid);     // project library
// neither settles – no result, no error after 120 s
```

The adapter sends `extensionApi.LIB_Footprint.getDocumentSource`, but nothing in the 3.2.209 client handles it.

**Expected:** the efoo source, or `undefined`, as documented. We need it to read a placed part's pad geometry; today we turn the part to 0°, read and turn it back.
````

## E-16 – [#51](https://github.com/easyeda/easyeda-api-sdk/issues/51)

### Title

```text
Feature request: getOpenDatabaseDoublePlusFile in millimetres
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client (pro-api 0.3.59).

`unit` admits `ESYS_Unit.INCH` only. With `ESYS_Unit.MILLIMETER` the archive still says `UNITS=INCH` in every file; File → Export → ODB++ in the GUI writes millimetres.

**Wish:** `unit` takes `ESYS_Unit.MILLIMETER` as the dialog does, and the method leaves beta.
````

## E-17 – [#52](https://github.com/easyeda/easyeda-api-sdk/issues/52)

Posted on 2026-11-01 on the owner's word, the same evening as the others. Checked before: 3.2.209 is the newest version, no issue there covers it, the calls follow the docs' example
(the schematic opened first, `@beta`); the lookup quoted from the client's bundle (pro-ui 3.2.198, `Hg.modifyName`).
Seen live for `modifySchematicName` with pytree; the other renames use the same lookup in the code.

### Title

```text
V3.2.209: dmt_Schematic.modifySchematicName returns false until the project tree has been shown once
```

### Body

````markdown
**Environment:** EasyEDA Pro 3.2.209, Linux desktop client, local projects (pro-api 0.3.59).

After a start of the client with another tab of the left panel open, every rename returns false, in every project:

```js
await eda.dmt_EditorControl.openDocument(pageUuid);    // as in the docs' example
await new Promise(r => setTimeout(r, 1000));
await eda.dmt_Schematic.modifySchematicName(schematicUuid, 'main');
// false, name unchanged – after one click on the project tree in the left panel: true, renamed
```

The handler looks the uuid up in the tree's rows (`rpcCall("getLeftTreeContentData")`, `findIndex(l => l.uuid === i)`, `-1` → `false`), and the tree has no rows before it was shown. `modifySchematicPageName`, `dmt_Pcb.modifyPcbName`, `dmt_Panel.modifyPanelName`, `dmt_Board.modifyBoardName` and `copyBoard` use the same lookup.

**Expected:** renaming works whatever the left panel shows.

**Workaround:** after every start we open the project tree once by hand.
````
