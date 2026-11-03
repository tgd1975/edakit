# Issue – draft (M-11)

Not posted – waits for the owner's word, with the pull request ([pr-10-net-read-one-page.md](pr-10-net-read-one-page.md)).
Checked before, on 2026-11-02: easyeda-mcp-pro 1.8.0 the newest release, `listNetsApi` unchanged on `upstream/main`
(`017f423`); no issue there covers it (searched "coordinate fallback net", "other schematic open net", "getAll
allSchematicPages", "net detail wrong pin"). Found live on pytree's `tree` the same day (E-18 before: taken for
EasyEDA's until the flag turned up).

### Title

```text
schematic: listNets/getNetDetail put a pin on a net flag of another open schematic
```

### Body

````markdown
**Environment:** easyeda-mcp-pro 1.8.0 (code unchanged on main 017f423), EasyEDA Pro 3.2.209, Linux.

A project with two schematics, both open; the first focused. `easyeda_schematic_net_detail {"netName": "V_LED", "scope": "focused"}` lists U4.11 on V_LED. In the focused schematic U4.11 has one wire, to (605, 1155), on U4_OUT6; it has no net flags at all. The other schematic has a V_LED flag at (605, 1155). Close its tab, and U4.11 is gone from V_LED.

`listNetsApi` takes the parts and flags from `SCH_PrimitiveComponent.getAll(undefined, true)` ([L896-L898](https://github.com/oaslananka/easyeda-mcp-pro/blob/017f423ae448eab377d9dc6e04fda7fa69add352/easyeda-bridge-extension/src/dispatcher.ts#L896-L898)), which returns every loaded page – here the other schematic's too –, but the wires from `SCH_PrimitiveWire.getAll()`, the focused page only ([L795](https://github.com/oaslananka/easyeda-mcp-pro/blob/017f423ae448eab377d9dc6e04fda7fa69add352/easyeda-bridge-extension/src/dispatcher.ts#L795)). The coordinate fallback joins them.

**Expected:** the focused read lists the focused page's nets only.

**Workaround:** we close every other schematic tab before we read.
````
