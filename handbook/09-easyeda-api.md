# 9 EasyEDA Pro API and MCP server: how they really behave

Everything here was found the hard way, on EasyEDA Pro 3.2.206 (Linux) with easyeda-mcp-pro 1.4.0, between
19 and 25 October 2026. edakit works around each point; this chapter explains why the code looks the way it does and
helps when you call the API directly.

Calls go through the MCP tool `easyeda_api_call` with `path` (e.g. `PCB_PrimitiveLine.create`) and `args` (a list).
List the available methods with `easyeda_api_inventory` and a `filter`.

## 9.1 Server and bridge

| Topic | Behaviour |
|---|---|
| `easyeda_api_call` | Needs `confirmWrite: true` **always**, also for pure reads. `easyeda_catalog_verify_device` writes to the local catalogue and needs it too. |
| Several servers | A second server (e.g. the one an edakit command starts) uses the same bridge connection as Claude Code's server – nothing needs to be disconnected. |
| Bridge timeout | Default 15 s per call; DRC and pour fills of a large board take longer. `BRIDGE_TIMEOUT_MS=120000` in `mcp-server.sh`. The server that holds the bridge port drops pending requests after **its** timeout ("stale sweep"), also requests another server passed through – so every server needs the same value. After changing it, restart all `easyeda-mcp-pro` processes. |
| npx | Do not start the server through npx: npx does not pass SIGTERM on, the server lingers as an orphan and blocks port 49620. `mcp-server.sh` installs a pinned version once and runs `node` directly. |
| Return depth | The original bridge extension cuts every `easyeda_api_call` answer after 5 levels (`[MaxDepth]`), fixed in the bundle, no setting. DRC details and the rule configuration are unreadable that way. `bridge-extension-patch.sh` raises it to 12. Then `PCB_Drc.check(true, false, true)` returns every finding per category (`Clearance Error`, `Connection Error`, …) with `errorObjType`, `ruleName`, `obj1`/`obj2` (`typeName`, `suffix` = "(net): eNNN"), `errData` (primitive ids, `position`, `minDistance`, `layerIds`). |
| Schematic PDF | The bridge's PDF export always calls the first available function, `PCB_ManufactureData.getPdfFile`; for a schematic nothing comes back, although `SCH_ManufactureData.getExportDocumentFile(name, "PDF"|"SVG"|"PNG")` can do it. The patch adds that path for `scope: "schematic"`. |
| BOM and netlist export | `easyeda_bom_export` writes no file and mixes all schematics of the project; the netlist export returns nothing. edakit writes both itself from the schematic primitives. |
| Exports | Export tools write only into the server's `ARTIFACT_DIR`; edakit starts its server with the directory it wants. The pick-and-place export returns xlsx even when csv is asked for. |
| Simulation tools | `easyeda_simulate_operating_point` / `_transient` know two diode models and no transistors – useless for a real circuit; edakit simulates with ngspice from the graph instead. |
| Part search | `easyeda_schematic_search_device` is a full-text search: `C5613` also finds `C5613331` and `UC5613PWP`. Take only hits whose `supplierId` is exactly the LCSC number. It returns no stock and no price. |

## 9.2 Editor state

| Topic | Behaviour |
|---|---|
| Active tab | Most tools act on the **active** document. If another tab is active, `easyeda_schematic_sheet_info` returns `SHEET_INFO_UNAVAILABLE`, and placing runs into the bridge timeout (`unconfirmed: true`) – check with a read whether something was placed after all. EasyEDA occasionally switches the tab by itself, so edakit checks the focus before writes (every write in the schematic, every 20 writes in the PCB) and gets the tab back or aborts. |
| Start page | Focus `tab_page1` means EasyEDA shows its start page; then every `DMT_*` query returns null. Open the project with `DMT_Project.openProject(<projectUuid>)`. |
| Local projects | `DMT_Project.getAllProjectsUuid` is **empty** for local projects – a closed project cannot be found by name. edakit remembers the UUID once it saw the project open. `modifyProjectDescription` and `modifyProjectFriendlyName` are placeholders (always false). |
| PCB tab "active" | The PCB editor answers `PCB_Drc.check`, `getDsnFile` and exports only after EasyEDA reported its tab as active – otherwise silently `undefined`/null. That report comes only on a tab switch; `openDocument` on the current tab does not help. Probe: `PCB_Drc.getCurrentRuleConfigurationName` (empty = inactive). Remedy: open the start page `tab_page1`, then the PCB again. |
| Throttling | Chromium throttles timers of covered windows; EasyEDA computes DRC, fills and exports in many small timer steps. With VS Code over EasyEDA the DRC of a 120-part board took more than 120 s and failed; unthrottled 1–4 s. Start EasyEDA with `--disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows`. |
| ELECTRON_RUN_AS_NODE | Every shell started from VS Code inherits it; EasyEDA (Electron) started from there behaves like Node ("bad option: --no-sandbox"). Start with `env -u ELECTRON_RUN_AS_NODE`. |
| Crashes | Long runs and big `batch_write` blocks crashed EasyEDA twice with V8 out-of-memory. edakit writes 40 operations per call and prints EasyEDA's memory per phase. |

## 9.3 Schematic

| Topic | Behaviour |
|---|---|
| Schematics | `DMT_Schematic.createSchematic()` → UUID (with page P1), `deleteSchematic(uuid)`, `copySchematic(uuid)` (complete; named `<name>_1` afterwards), `DMT_EditorControl.openDocument(pageUuid)` activates a page. |
| Renaming | `modifySchematicName(uuid, name)` renames the **active** schematic, not the one passed. Right after `createSchematic` it reports true and does nothing. Activate the page first, rename, then check all names. Never delete anything when names look wrong – it might be the wrong schematic. |
| Reading names | `getAllSchematicsInfo` returns names partly stale or lower-case – read each name with `getSchematicInfo(uuid)`. Right after creation that throws `reading 'Symbol'` for a moment. |
| Board link | A schematic that belongs to a board (`parentBoardName`) must never be deleted or replaced: the PCB would lose its schematic. |
| Coordinates | y points **up** on screen (the tool says `yAxis: down`). Pin x/y = pin tip, pin rotation = direction pointing out (0 = +x, 90 = +y). Part rotation is counter-clockwise. |
| Moving | `modify_primitive` reports `followedWireIds`, but the wires stay where they were – the connection breaks. So: delete wires, move, draw again. |
| Net connections | `connect_pins_by_net` draws a short stub with the net name per pin – ERC and ratsnest see the connection. It silently skips a pin whose stub end would land on a point that already belongs to another net; a longer stub fixes it. |
| Flags | `SCH_PrimitiveComponent.createNetFlag(kind, net, x, y, rot)`. Ground points to −y at 0, power to +y; the rotation turns clockwise. |
| Wires | `SCH_PrimitiveWire.create([[x1,y1,x2,y2], …], net)` – one wire may branch (junction dots at T joints automatically). A crossing with four branches → `create failed!`. Touching wires of the same net merge. |
| `batch_write` | Atomic per call; fails on merging wires and on `modify` without a change (`cmdKey`). `addIntoBom: false` on create fails for library parts ("Invalid device") – create, then modify. |
| Netlist after writes | Right after many writes `easyeda_schematic_nets` sometimes returns nothing (0/88 nets, two minutes later 88/88). Wait and read again. |
| ERC | Nets with one pin (partial builds) give warnings, not errors. |
| Texts | `SCH_PrimitiveText.delete` and `.modify` act only until the page is reloaded: only creating is saved. After every run another layer of titles and notes was on the page (100 texts on one sheet). `SCH_PrimitiveCircle.delete([textIds])` (or `…Component`/`…Wire.delete`) deletes texts for good. PCB texts and schematic rectangles, wires, flags and attributes are not affected. |
| Orphan attributes | Deleting a part or a net flag through the API leaves its attribute texts (designator, name, pin texts) on the page; their parent id is `<part>-e<n>`. Delete them explicitly. |
| Page size | New pages are A4. `DMT_Schematic.modifySchematicPageTitleBlock(page, {Width: {value}, Height: {value}})` plus the field `Page Size`. Standard sizes in 10-mil units: A4 1170 × 825, A3 1654 × 1170, A2 2339 × 1654, A1 3311 × 2339, A0 4681 × 3311. |
| Title block | `modifySchematicPageTitleBlock(page, {field: {value}})`. Shown: Company, Drawn, Reviewed, Version, Page Size; the big centre cell shows the project name, `Page` the page name (`modifySchematicPageName`). `getSchematicPageInfo` returns new values only after a while. |
| Sheet frame | The title block belongs to the frame, a component of type `sheet` (`SCH_PrimitiveComponent.getAll("sheet")`). Without it `titleBlockData` is empty. Create one with the system device "Drawing-Symbol_A4" (`LIB_Device.search("Drawing-Symbol")`) – it appears at once, but the answer never comes; use a short timeout and look. |
| Rectangles, texts | `SCH_PrimitiveRectangle.create(left, top, width, height, radius, rot, colour, fill, line width, line type)` – height goes towards −y, line type 1 = dashed. `SCH_PrimitiveText.create(x, y, text, rot, colour, font, size, bold, italic, underline, alignMode)` – `\n` for several lines; alignMode 3: (x, y) = bottom of the **last** line, 1: top left. |
| Opening a big page | A 120-part A1 page took up to 160 s until it was active. A timeout while opening does not mean it failed. |

## 9.4 PCB

| Topic | Behaviour |
|---|---|
| Units | mil, y up. Pour fills (`PCB_PrimitivePoured … PourFills`) come in **10 mil** units, everything else in mil. |
| Netlist → PCB | `PCB_Document.importChanges(uuid, true)` opens the confirmation dialog anyway (`force` has no effect). Pure net changes without dialog: `PCB_PrimitivePad.modify(padId, {net})` (pads of parts have their own ids from `getAllPinsByPrimitiveId`). |
| Parts without dialog | `PCB_PrimitiveComponent.create({libraryUuid: <project>, uuid: <device>}, layer, x, y, rot, lock)` creates the part without designator link (e.g. `BUZZER1`, empty UniqueId). Then `modify(id, {designator, uniqueId, otherProperty})`. `uniqueId` = UniqueId of the same part in the schematic – that is the link. `otherProperty` replaces **all** properties, so pass the complete set incl. `Channel ID` (no fixed rule; take the next free `$1I<n>`). The properties must come from the **schematic**, not the library: if e.g. the Description differs, the DRC reports "Netlist Error – Import Changes" (it compares like the dialog). To swap a part, delete the old one first – its tracks stay. |
| The one click left | When a part was freshly placed in the **schematic** from the library, the DRC reports "Netlist Error – Import Changes" until the import view was opened once in the GUI (it shows "no changes"). `importChanges()` through the API, `LIB_Device.get` and reloading do not help. |
| Net classes | `PCB_Drc.createNetClass(name, nets, {r,g,b,alpha})` returns false as soon as one net is missing in the PCB; alpha is read as 0–255. Track rules are easier to set in the GUI (Design → Design Rule); the mapping net class → rule through `getNetRules`/`overwriteNetRules`. |
| Auto-layout | `PCB_Document.autoLayout` places only unlocked parts, only on TOP, knows nothing about which capacitor belongs to which IC, and keeps running after the bridge timeout. |
| Autorouter | `PCB_Document.autoRouting` keeps its result only if the whole run succeeds; on abort or error it discards everything (API docs; observed: 1773 lines → 223). Fixed 900 s limit, runs past the bridge timeout, sometimes does not start, left nets open, routes nothing on nets that are partly routed. Use Freerouting. |
| DSN/SES | `PCB_ManufactureData.getDsnFile` returned null (tab "inactive"); `importAutoRouteSesFile` needs a `File` object the bridge cannot pass. edakit writes the DSN itself and creates tracks and vias from the SES. |
| Tracks, vias, texts | `PCB_PrimitiveLine.create(net, layer, x1, y1, x2, y2, width, lock)`, `PCB_PrimitiveVia.create(net, x, y, drill, diameter, 0, "", null, false)`, `PCB_PrimitiveString.create(layer, x, y, text, font, size, line width, align, rot, invert, expand, mirror, lock)` – all in mil. |
| Creating tracks | Pieces shorter than ~0.5 mil are dropped; straight consecutive pieces of a net (kink up to ~0.3 mil) are merged into one. Counting after creation is no check – compare geometrically. Track to track connects only through ends that coincide to ~0.01 mil (0.02 mil off = "disconnected"); at pads and vias it is enough that the end lies inside. Pieces completely inside a via are dropped. |
| Deleting tracks | `PCB_Document.clearRouting` runs into a dialog timeout. Delete with `PCB_PrimitiveLine`/`PCB_PrimitiveVia.delete` and id lists – then count again: deleting sometimes needs a second pass, and old tracks reappeared after a reload. |
| DRC after API changes | Reports false "Connection Error"s on correct tracks as long as the PCB was not saved and reloaded (320 errors, minutes later still; reloaded: 0). Save, `DMT_EditorControl.closeDocument(tabId)`, `openDocument(pcbUuid)`. |
| DRC result | `PCB_Drc.check(true, false, true)` with details always returns a list (`[]` = no findings); null means it did not run. |
| Pours | `PCB_PrimitivePour.create(net, layer, {$polygon}, "solid", preserveIslands, name, priority, line width)`. A `$complexPolygon` with a hole is taken only as its outer contour, and filling fails then. Fill with `easyeda_pcb_rebuild_copper` (per net); its status `readback-mismatch` is harmless (it compares only the returned id). Whether it filled: `PCB_PrimitivePoured.get(<pourId>)` → `PourFills`. |
| Free pads | `PCB_PrimitivePad.create(12, "TL1", x, y, 0, ["ELLIPSE", d, d], "", ["ROUND", d], 0, 0, 0, false, 0, [], {topSolderMask, bottomSolderMask, topPasteMask, bottomPasteMask}, null, true)` creates a pad without part; non-plated it lands in `Drill_NPTH_Through.DRL`, without a copper ring when pad and hole have the same size – a JLCPCB tooling hole. **While such a pad is in the PCB, `easyeda_pcb_rebuild_copper` fails** ("Cannot read properties of undefined (reading 'length')"), whatever its settings; DRC and export work. So take tooling holes out before filling and put them back after. |
| Designators | Attributes (`PCB_PrimitiveAttribute`, key `Designator`). `modify(id, {valueVisible, x, y, rotation, alignMode: 5, fontSize})` works on locked parts too; alignMode 5 = centre at x/y. Stroke font `default`: 0.5–0.6 × height per character. Size of any primitive: `PCB_Primitive.getPrimitivesBBox`. |
| Bottom silkscreen | EasyEDA mirrors **texts** on the bottom silk layer itself (create with `mirror = false`, with true they read mirrored from outside). It does **not** mirror graphics (fills, lines) – mirror those yourself. |
| Footprint geometry | Turning a part to 0° on TOP and reading pads relative to its origin gives the library geometry; on the bottom side EasyEDA mirrors local y, then rotates. |
| Footprints in the project | Editing: `LIB_Footprint.openInEditor(fp, <project UUID>)` (with "project" it fails), then `PCB_PrimitivePad.modify/delete` in the editor, `PCB_Document.save`, close the tab. Placed parts keep their embedded copy until deleted and recreated. `LIB_Footprint.copy` creates a footprint without device, `LIB_Device.copy/create` give unusable devices. `LIB_Footprint.getDocumentSource` hung for minutes. Changing pins through the graph (e.g. swapping which net goes to which pad) was the faster way than repairing a library footprint. |
| View | `DMT_EditorControl.zoomTo(x, y, zoom)` centres at (x, y) at zoom/100 px per unit; the `bottom` in its return value is wrong. Canvas images come as an MCP image block. |

## 9.5 Gerber export (what edakit reads)

- Files: `Gerber_TopLayer.GTL`, `Gerber_BottomLayer.GBL`, silk `GTO/GBO`, mask `GTS/GBS`, outline `GKO`, drills
  `Drill_PTH_Through.DRL`, `Drill_PTH_Through_Via.DRL`, `Drill_NPTH_Through.DRL`, plus `FlyingProbeTesting.json` with
  every pad (position, size, layer, name `<designator>_<pin>`).
- No net attributes (`%TO.N`) in the Gerber files; FlyingProbeTesting.json renames some nets (`NET_3`). Take the net
  of each pad from the graph.
- Pads are always apertures (flashes), never regions. Pours are regions, and EasyEDA traces the edge of every pour as a
  line on top.
- The mask layers use the aperture macro `RoundRect`.
- Gerber coordinates are EasyEDA's coordinates in mm.
