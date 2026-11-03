# Upstream: what edakit needs from EasyEDA Pro and easyeda-mcp-pro

edakit drives EasyEDA Pro through [easyeda-mcp-pro](https://github.com/oaslananka/easyeda-mcp-pro). Whatever edakit
has to click, patch or work around because one of the two lacks something or gets it wrong is a requirement here –
E-… for EasyEDA Pro, M-… for easyeda-mcp-pro – and stays here until upstream has released the fix and edakit has
dropped its workaround. How each behaves today is in [handbook 9](../handbook/09-easyeda-api.md); this list says what
we want instead and where it stands. Nothing here is posted without the owner's word.

## The owner's rules (2026-11-01)

1. **No click because of the API.** The owner never has to press anything in EasyEDA Pro because its API gets
   something wrong or leaves it out. Every click edakit still asks for has its requirement below, reported at
   EasyEDA, until the API takes it over.
2. **No self-extended MCP server.** edakit patches easyeda-mcp-pro no further: what it needs goes upstream as an issue
   and a pull request from the fork [tgd1975/easyeda-mcp-pro](https://github.com/tgd1975/easyeda-mcp-pro). The two
   patches edakit had – `odb-tool-patch.mjs` and `bridge-extension-patch.sh` – went with 1.7.0, which brought M-2 to
   M-4; no new patch comes.
3. **The latest state first.** Before a requirement is reported, a branch is built or a workaround is changed, the
   check below runs. A requirement upstream has met already is not reported but taken up: the pin raised, the
   workaround removed.

## The latest state

1. easyeda-mcp-pro: in the clone `../easyeda-mcp-pro` `git fetch upstream`; the newest release
   (`npm view easyeda-mcp-pro version`) against the pin `EASYEDA_MCP_VERSION` in `edakit/easyeda/mcp-server.sh`, its
   `CHANGELOG.md` since the pin, and the source on `upstream/main` where the fix would sit. Issues and pull requests,
   open and closed: `gh search issues --repo oaslananka/easyeda-mcp-pro "<topic>"`.
2. EasyEDA Pro: the newest version on its [update record](https://pro.easyeda.com/page/update-record) against the
   installed one (`ls /opt/apps/easyeda-pro/resources/app/assets/pro-versions`), the issues of
   [easyeda/easyeda-api-sdk](https://github.com/easyeda/easyeda-api-sdk/issues), open and closed – mostly in Chinese;
   EasyEDA's first answer is "update to the latest version" –, and the API types
   (`npm view @jlceda/pro-api-types version`). An E-… is checked live on the newest version before it is reported,
   each call in it against the docs first (below, "How EasyEDA takes reports").
3. The fork's branches rebased onto `upstream/main`, their tests green.
4. The column "Checked" takes the version checked against.

**Last check, 2026-11-02:**

- E-18 (TD-105): EasyEDA Pro 3.2.209 is still the newest (update record, 2026-11-02), pro-api 0.3.59, the types on npm 0.4.27; no issue at easyeda/easyeda-api-sdk names it. Live on pytree the cause is easyeda-mcp-pro's, not EasyEDA's – M-11, the fork's branch `fix/net-read-one-page`.
- easyeda-mcp-pro 1.7.0 and 1.8.0 were released on 2026-11-02 (the tags `easyeda-mcp-pro-v1.7.0`, `…-v1.8.0`): 1.7.0
  brings #809 (M-1, M-5, M-7), #810 (M-2), #812 (M-3), #814 (M-9), #815 (M-4) and our #819 (M-10); 1.8.0 adds relay
  connection modes and PCB text defaults, nothing edakit needs. edakit pins 1.8.0 (TD-26, TD-84): both patches gone,
  the workarounds of M-2, M-3, M-4, M-7, M-9 and M-10 taken up – checked against the source of 1.8.0 and live the same
  evening with the extension of 1.8.0 imported, on EasyEDA Pro 3.2.209 and `examples/coin-cell-led`: `edakit doctor`
  (extension 1.8.0 = server 1.8.0), `schematic create --save` with BT1 `bom: false` (no modify after the create,
  SYNC.bom green), `route pours` (GND top and bottom in one call, rebuilt and verified), `route drc` (0), `gate
  --easyeda` (S, L, F passed: SYNC.cpl from the csv, GEO.drc with the rule set at depth 12, SYNC.odb from
  `easyeda_export_odb`), `export` (vector schematic PDF, `cpl_main.csv`). How each is met: M-3 – `easyeda_api_call` takes `maxDepth`
  1 to 16, default still 5 (`src/tools/L0_diagnostics_api.ts:21`, extension `api-runtime.ts:28`); edakit asks 12 on
  every call. M-4 – `easyeda_export_odb` is registered in the profile `experimental` only
  (`src/tools/L1_export.ts:819`), so edakit's own servers run that profile; the archive is EasyEDA's tgz in inch
  (extension `export-operations.ts:93`). M-9 – the flags are applied after `create` best-effort (extension
  `dispatcher.ts:1053`); edakit reads `addIntoBom` back. M-1 – each request keeps its own timeout
  (`src/bridge/manager.ts:131`); the default is still 15 s, so `BRIDGE_TIMEOUT_MS=120000` stays, no longer the same in
  every server. M-5 – edakit's name check stays: it guards which project is open, not only a failed create. 1.7.0 is
  the first release under MIT.

**Check of 2026-11-01:**

- In the evening `upstream/main` (`9601584`) carries the fixes of M-1 to M-5, M-7 and M-9, built by the maintainer
  after our pull requests: #809 (M-1, M-5, M-7), #810 (M-2), #812 (M-3, `maxDepth`), #814 (M-9), #815 (M-4,
  `easyeda_export_odb`, experimental). Our pull requests are closed, the issues too but #796 and #798 – "not included
  in the currently published v1.6.0". No release yet: the pin, both patches and the workarounds stay until one
  comes (TD-26). The rebuild code of M-10 is unchanged there.
- easyeda-mcp-pro 1.6.0 (2026-10-28) is the newest; edakit pins it (TD-25; 1.4.0 before). Nothing from 1.4.0 to
  1.6.0 meets M-1 to M-4 – on `upstream/main` the return depth is still 5, the PDF export still calls the PCB's
  function first, there is no ODB++, the stale sweep in `src/bridge/manager.ts` is unchanged – and no issue or pull
  request there covers them. Since 1.5.1 the
  server refuses writes from a bridge extension of another version: raising the pin takes the extension of the same
  version, imported anew (E-4). The anchors of both patches are still in 1.6.0; both applied, the patched extension
  built (`~/.easyeda-mcp-pro/easyeda-bridge-extension-1.6.0.eext`). Since 1.6.0 the PCB lists
  (`easyeda_pcb_components`, `_tracks`, `_vias`, `_regions`, `_fills`) answer only with the PCB focused and the
  project's exact UUID as `projectId` – edakit's `list_pcb_components` passes it.
- The fork's three branches rebased onto 1.6.0 (`e52d862`); their tests in the table of the branches below.
- EasyEDA Pro 3.2.209 (2026-10-21) is the newest and, since 2026-11-01, installed (in place from the zip; 3.2.206
  unpacked in `~/Downloads/easyeda_unzipped` as the way back); it brings pro-api 0.3.59 (3.2.206: 0.3.50), the
  types on npm are 0.4.27. E-1 to E-16 checked live on it the same day, with the bridge of 1.4.0 – the results in the
  tables. Methods documented "ADD since EDA v4.1.79" (`waitForDocumentReady`, `getDocumentReadyState`,
  `startAutoLayout`, …) hang on 3.2.209.
- EasyEDA has published an AI skill with a WebSocket bridge of its own,
  [easyeda/easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill) – not examined.

## EasyEDA Pro – its extension API

Reported at [easyeda/easyeda-api-sdk](https://github.com/easyeda/easyeda-api-sdk/issues): to a known issue our case
as a comment, otherwise an issue of its own. Posted on 2026-11-01 on the owner's word, after the live check on
3.2.209: #45 to #51 and comments to #36 and #38, #52 (E-17) the same evening, the texts as posted in [easyeda-reports.md](easyeda-reports.md).

**How EasyEDA takes reports.** The repository has no template and no contribution guide; its issues are mostly
Chinese, the maintainers answer in Chinese and read English. They turned reports away whose calls did not follow the
documentation – "你使用 AI 生成的案例是错误的，传参并不符合文档规定" (#31), "使用 AI 提单时请人工校对一遍文档的说明" (#30).
So before an E-… is reported, every call in it is checked against the JSDoc of the client's own types
(`/opt/apps/easyeda-pro/resources/app/assets/pro-api/<version>/api-types.d.ts`: parameters, `@remarks`, the
example, `@internal`, "ADD since"); the check of 2026-11-01 turned four requirements into our own errors or into
documented behaviour (E-2's Channel ID, E-8, E-9, E-13). A report: English, short; the title
`V3.2.xxx: <method> <what happens>` for a defect, `Feature request: …` for a wish; environment, the call, what
happens, what is expected, the workaround.

### The clicks

| # | Requirement | The click today | Handbook | Upstream | Checked |
|---|---|---|---|---|---|
| E-1 | `DMT_Project.createProject` creates a project in the local desktop client – its local server wants a folder `path` the API cannot pass | *File → New → Project*, once per project | 9.2 Creating projects | [#45](https://github.com/easyeda/easyeda-api-sdk/issues/45), posted 2026-11-01 – the API's `createProject` sends `path: undefined`, also with the project folder as `teamUuid`; M-5 is the server's part | 3.2.209 |
| E-2 | Import Changes without the dialog: `PCB_Document.importChanges(uuid, true)` honours `uuid` and `force` | none since 2026-11-01 (TD-37): `pcb parts --write` writes the Channel ID into the schematic part, `route`/`silk` into parts linked before; the click only if the DRC still reports the item | 9.4 The one click left, Netlist → PCB | [#46](https://github.com/easyeda/easyeda-api-sdk/issues/46), posted 2026-11-01 – the handler reads only `source` and drops `uuid` and `force`. The DRC's "Netlist Error" after parts placed through the API is ours: the import compares the Channel ID, an attribute edakit can write into the schematic part too – then the DRC is clean without the import view (live); not reported, taken up (TD-37, live 2026-11-01) | 3.2.209 |
| E-3 | Calls address a document by its UUID, whichever tab is active: the PCB answers `PCB_Drc.check`, `getDsnFile` and the exports without its tab counting as active; schematic reads and writes act on the page named | edakit switches to the start page and back; when that fails, "click the PCB tab once" | 9.2 Active tab, PCB tab "active" | not reported, watched – not reproduced on 3.2.209: after `openDocument(pcb)` the PCB answers at once; with the schematic active the PCB call now throws ("指定的主题消息在对应的画布内没有相关订阅") instead of returning empty – `activate_pcb` takes that as inactive (TD-38, live 2026-11-01) | 3.2.209 |
| E-4 | Install and update an extension without the GUI – a command-line option, a folder the client reads, or an API call | for every bridge extension: uninstall, import, allow "External interaction", restart – since easyeda-mcp-pro 1.5.1 at every update of the server | 2.5 | [#47](https://github.com/easyeda/easyeda-api-sdk/issues/47) (feature request), posted 2026-11-01 – no command-line option, folder or call; the extension survives a client update | 3.2.209 |
| E-17 | Renaming a schematic or page through the API works whatever the left panel shows: `modifySchematicName` and `modifySchematicPageName` look the UUID up in the rows of the project tree, which exist only after the tree was shown once | after every start of EasyEDA: open the project tree in the left panel once | 9.2 Renaming | [#52](https://github.com/easyeda/easyeda-api-sdk/issues/52), posted 2026-11-01 – [as posted](easyeda-reports.md); found 2026-11-01 on 3.2.209 (pytree and coin-cell-led; bundle pro-ui 3.2.198: `Hg.modifyName` → `getLeftTreeContentData`, the tree's `passContentData` builds nothing before its first render); the API way, `SYS_PanelControl.openLeftPanel`, is closed by easyeda-mcp-pro's bridge (no `SYS_` class allowed) | 3.2.209 |

### Defects edakit works around

| # | Requirement | edakit's workaround | Handbook | Upstream | Checked |
|---|---|---|---|---|---|
| E-5 | `SCH_PrimitiveText.delete` and `.modify` are saved | deletes texts through `SCH_PrimitiveCircle.delete` | 9.3 Texts | [#36](https://github.com/easyeda/easyeda-api-sdk/issues/36) (open) – our comment of 2026-11-01: `modify` is lost too; `SCH_PrimitiveCircle.delete` of a text is saved | 3.2.209 |
| E-6 | `PCB_Document.clearRouting` ends without a dialog | deletes lines and vias by id and counts again | 9.4 Deleting tracks | [#38](https://github.com/easyeda/easyeda-api-sdk/issues/38) (open) – our comment of 2026-11-01: no answer after 120 s, no dialog, nothing cleared | 3.2.209 |
| E-7 | The DRC is right after API writes without save, close and reopen | saves, closes and reopens only when the DRC reports Connection Errors, then runs it once more | 9.4 DRC after API changes | met on 3.2.209, not reported: a track deleted → DRC false, created again → true, without save and reload; on a PCB never reloaded since EasyEDA's start, pours refilled and tooling holes replaced: DRC 0 – taken up (TD-38, 2026-11-01); a full routing run without reload is the next project's | 3.2.209 |
| E-8 | `modifySchematicName(uuid, …)` renames the schematic passed; `getAllSchematicsInfo` returns current names and lists a document as soon as it exists | activates, renames, reads every name back, checks the panels | 9.3 Renaming, Reading names | met or documented on 3.2.209, not reported: renames the schematic passed, not the active one; the 1.5 s wait and lower-case names are in the docs' examples; edakit's checks stay | 3.2.209 |
| E-9 | Local projects: `getAllProjectsUuid` lists them; `modifyProjectDescription` and `modifyProjectFriendlyName` work | – (rename and description: none, edakit needs neither) | 9.2 Local projects | `getAllProjectsUuid(teamUuid)` with the project folder (`DMT_Team.getAllTeamsInfo`) lists local projects – documented, our call lacked it; taken up on 2026-11-01 (TD-39), checked live: the three projects and the five examples of both folders. Rename and description: [#48](https://github.com/easyeda/easyeda-api-sdk/issues/48) (feature request; `@internal`, suspended since 2024) | 3.2.209 |
| E-10 | Deleting a part or a net flag deletes its attribute texts | deletes them by their parent id – kept as a cheap sweep for pages from before | 9.3 Orphan attributes | met on 3.2.209, not reported: a part's 36 and a net flag's 9 attributes go with it, none left after save and reopen; taken up (TD-40) | 3.2.209 |
| E-11 | Footprints: a placed part takes its edited footprint without being deleted and placed anew; a device made by `LIB_Device.create` or `copy` can be placed in the local client; `SCH_PrimitivePin.modify` is saved | `edakit part build` rebuilds the copy of a system part – its symbol's pins modified in place –, the parts are placed anew | 9.4 Footprints in the project | [#49](https://github.com/easyeda/easyeda-api-sdk/issues/49) (feature request: update placed parts to the edited footprint). `SCH_PrimitivePin.modify` is saved on 3.2.209 – taken up; `LIB_Device.copy` throws, the bridge passes only "[object Object]" – not reported | 3.2.209 |
| E-12 | A placed part's footprint geometry is readable without turning or moving the part | turns it to 0° on TOP, reads, turns it back | 9.4 Footprint geometry | [#50](https://github.com/easyeda/easyeda-api-sdk/issues/50), posted 2026-11-01 – `lib_Footprint.getDocumentSource`, the documented way to read footprint geometry, never answers: no handler in the 3.2.209 client | 3.2.209 |
| E-13 | Pours: a `$complexPolygon` with holes is filled as drawn; filling works while a non-plated pad without part – a tooling hole – is on the board | none since 2026-11-01 (TD-40): tooling holes stay while the pours fill, a `NO_POURS` region keeps each hole free instead of a notch (the region's name is not kept – edakit remembers the ids) | 9.4 Pours, Free pads | not reported: with NPTH tooling holes (TL1, TL2) the fill works on 3.2.209; a hole in a pour is a region with `NO_POURS` (`EPCB_PrimitiveRegionRuleType` 7), not an inner contour – the docs show `createComplexPolygon` with separate pieces only; taken up | 3.2.209, 1.4.0 |
| E-14 | `PCB_Document.autoLayout` places on both sides | parts on the bottom are placed by the plan (`[place]`) | 9.4 Auto-layout | not reported: `autoLayout()` takes no parameter (documented); bottom parts come from the plan, no click | 3.2.209 |
| E-15 | `addIntoBom: false` works when a library part is created | none since easyeda-mcp-pro 1.7.0 (M-9): set on create, read back | 9.3 `batch_write` | not EasyEDA's: `SCH_PrimitiveComponent.create(…, mirror, addIntoBom, addIntoPcb)` works on 3.2.209; easyeda-mcp-pro's bridge drops the three – M-9 | 3.2.209, 1.4.0 |
| E-16 | ODB++: `getOpenDatabaseDoublePlusFile` out of BETA and in millimetres as the dialog writes it – its `unit` admits `ESYS_Unit.INCH` only | SYNC.odb reads either unit | 9.1 ODB++ | [#51](https://github.com/easyeda/easyeda-api-sdk/issues/51) (feature request), posted 2026-11-01 – `"mm"` (= `ESYS_Unit.MILLIMETER`) still gives `UNITS=INCH` in every file; typed INCH only, `@beta` | 3.2.209 |
| E-18 | A schematic's netlist lists each pin on the nets of that schematic's primitives, whatever other schematic of the project is open | – (the workaround is M-11's) | 6.2 | not EasyEDA's, not reported – the bridge's: checked live on 2026-11-02 on 3.2.209, the newest, with 1.8.0 on pytree's `tree` (TD-105). The template `generated_tree` has no net flag; the board's schematic `layout_tree` has a V_LED flag at (605, 1155), the end of the template's wire from U4.11 to U4_OUT6. `SCH_PrimitiveComponent.getAll(…, true)` returns every loaded page – documented (`@remarks`: "只返回已加载图页中的器件"), here the other schematic's too: 85 components with the template alone, 244 with both open –, `SCH_PrimitiveWire.getAll(net?)` the focused page's wires only; easyeda-mcp-pro's coordinate fallback joins the two (M-11) | 3.2.209 |

E-2 (the query whether an import is pending), E-3 (writing by document id) and E-11 to E-15 come from the analysis
of the project histories that pytree-27 left in the owner's TODO list.

## easyeda-mcp-pro

An issue first, then the fork's branch and its pull request with "Fixes #<issue>" – M-1 to M-4 so posted on
2026-11-01, M-5 and M-7 the same day (their pull requests on the owner's question whether we had fixes), M-9 too, M-10 the same evening (#818, #819), the texts as in the drafts. **Short, as a person writes them:** an issue says the environment, what
happens, what is expected and the workaround; a pull request its Summary, Risk and Validation – the template asks no
more of a first contribution, the maintainer fills its checklists himself; no "Generated with Claude Code" line
(the owner, 2026-11-01). The pattern: #468 and #527 there, under
1000 characters each; the owner found the first, long texts too long and machine-like (2026-11-01). The same for reports to
EasyEDA. On the first substantial pull request
the maintainer asked once for the comment "I agree to the Contributor Permission v1 in CONTRIBUTOR-LICENSING.md" from
the account that opened it – a consent in the owner's name, given by the owner. Gone since 2026-11-01: upstream's
`caa931c` (#806) took the project back from PolyForm Noncommercial 1.0.0 to MIT and dropped the contributor permission;
1.1.0 to 1.6.0 stay PolyForm Noncommercial; 1.7.0 is the first release under MIT, and with the pin of 1.8.0 the licence
notes followed: `docs/how-it-works.md` (State), `handbook/02-setup.md` 2.8, `handbook/16-kicad.md`; the concepts
`docs/concepts/new/outreach.md` and `docs/concepts/done/kicad-toolchain.md` keep the state they were written in.

| # | Requirement | Local workaround – goes with the release (taken up with 1.8.0: "gone") | Upstream | Fork branch | Checked |
|---|---|---|---|---|---|
| M-1 | The stale sweep honours each request's own timeout | `BRIDGE_TIMEOUT_MS=120000` stays – the default is still 15 s –, no longer the same in every server | [#792](https://github.com/oaslananka/easyeda-mcp-pro/issues/792), [#793](https://github.com/oaslananka/easyeda-mcp-pro/pull/793) – [drafts](issue-1-stale-sweep.md); fixed on main by #809, released in 1.7.0 | `fix/stale-sweep-per-request-timeout` | 1.8.0 |
| M-2 | `easyeda_export_pdf` with `what: "schematic"` exports the schematic | gone: `bridge-extension-patch.sh` removed | [#794](https://github.com/oaslananka/easyeda-mcp-pro/issues/794), [#795](https://github.com/oaslananka/easyeda-mcp-pro/pull/795) – [drafts](issue-2-schematic-pdf.md); #527 (closed) only stopped the false success; fixed on main by #810, released in 1.7.0 | `fix/schematic-pdf-export` | 1.8.0 |
| M-3 | `easyeda_api_call` returns deeper results (`maxDepth`) – DRC details and the rule set lie 9 levels deep | gone: `bridge-extension-patch.sh` removed; edakit passes `maxDepth: 12` (`eda.API_DEPTH`) | [#796](https://github.com/oaslananka/easyeda-mcp-pro/issues/796), [#797](https://github.com/oaslananka/easyeda-mcp-pro/pull/797) – [drafts](issue-3-api-call-depth.md); fixed on main by #812, released in 1.7.0 | `feat/api-call-max-depth` | 1.8.0 |
| M-4 | ODB++ export as a tool | gone: both patches removed; edakit's own servers run the profile `experimental`, where the tool is registered | [#798](https://github.com/oaslananka/easyeda-mcp-pro/issues/798), [#799](https://github.com/oaslananka/easyeda-mcp-pro/pull/799) – [drafts](issue-5-odb-export.md); fixed on main by #815, released in 1.7.0 | `feat/odb-export` | 1.8.0 |
| M-5 | `easyeda_api_call` reports a create call that returns null as a failure | none left: the project's name is checked before every run for which project is open, not for this | [#800](https://github.com/oaslananka/easyeda-mcp-pro/issues/800), [#802](https://github.com/oaslananka/easyeda-mcp-pro/pull/802) – [as posted](issue-4-create-project.md); fixed on main by #809, released in 1.7.0 | `fix/api-call-null-create` | 1.8.0 |
| M-6 | The schematic read tools and the BOM read a page by its UUID without switching the owner's tab; the BOM of a board-linked schematic lists each part once | focuses page after page, merges, checks the focus after each read | met as far as EasyEDA lets it: #539, merged on 2026-08-26 and in 1.4.0 already, gives the read tools `scope` and `pageUuid`; `page` fails closed where EasyEDA's API reads only the active page – that is E-3. Live on 1.6.0 (2026-11-01): `all_pages` of `easyeda_schematic_components` is `SCH_PrimitiveComponent.getAll(…, true)` and answers with the parts of every open schematic of the project – the template's beside the board's, without the page of each part –, so edakit stays page by page (TD-53); the BOM of a board-linked schematic lists each part once – edakit's removal of the duplicates went, SYNC.bom reports a designator listed twice (TD-54). Not reported | – | 1.6.0 |
| M-7 | The pick-and-place export returns csv when csv is asked: the bridge passes the project id as the file name and no type to `getPickAndPlaceFile(fileName, fileType, unit)`, so EasyEDA answers with its default xlsx | gone: the csv is read; an xlsx of an older extension too | [#801](https://github.com/oaslananka/easyeda-mcp-pro/issues/801), [#803](https://github.com/oaslananka/easyeda-mcp-pro/pull/803) – [as posted](issue-7-pick-place-csv.md); fixed on main by #809, released in 1.7.0 | `fix/pick-place-file-type` | 1.8.0 |
| M-8 | The bridge connects by itself, also after a crash of EasyEDA, and shows its menu | the skill start asks for *MCP Bridge → Connect*, or restarts EasyEDA | report only if the original extension does it too – after a re-import the menu is sometimes missing | – | 1.4.0 |
| M-9 | `easyeda_schematic_place_component` and `batch_write` set `mirror`, `addIntoBom` and `addIntoPcb` of a placed part | gone: `addIntoBom` on create, read back after placing (the bridge applies it best-effort) | [#804](https://github.com/oaslananka/easyeda-mcp-pro/issues/804), [#805](https://github.com/oaslananka/easyeda-mcp-pro/pull/805) – [as posted](issue-8-place-component-flags.md). Reproduced on 2026-11-01 with EasyEDA Pro 3.2.209 and the bridge of 1.4.0, the code unchanged on 1.6.0: `batch_write` reports `applied`, the part keeps `Mirror: false`, `AddIntoBom` and `AddIntoPcb: true` – the bridge calls `create(deviceItem, x, y)` and applies only `rotation` afterwards. Not "Invalid device": `needDevice()` turns away only device ids `LIB_Device.get` does not know, whatever `addIntoBom` says; fixed on main by #814, released in 1.7.0 | `fix/place-component-flags` | 1.8.0 |
| M-10 | `easyeda_pcb_rebuild_copper` fills a net's fresh pours in one call without locking every later rebuild – today EasyEDA's beta `rebuildCopperRegion` answers the second pour with the first one's copper, the result is `readback-mismatch`, and the bridge refuses all rebuilds until EasyEDA restarts | gone: a net's fresh pours in one call; still stops with "restart EasyEDA" when the bridge refuses | [#818](https://github.com/oaslananka/easyeda-mcp-pro/issues/818), [#819](https://github.com/oaslananka/easyeda-mcp-pro/pull/819), posted 2026-11-01, merged, released in 1.7.0 – [as posted](issue-9-rebuild-copper.md); found 2026-11-01 on 1.6.0 (coin-cell-led: per net the second pour mismatched; one fresh pour per call verified). A refill of a filled pour mismatches too – not edakit's case, left out (the owner, 2026-11-01) | `fix/rebuild-copper-batch-reconcile` | 1.8.0 |
| M-11 | `easyeda_schematic_net_detail` and `schematic.listNets` read the focused page only – today a net flag of another open schematic of the project that sits on a wire point of the focused page joins that wire's net | `schematic check` and stage S close every saved schematic tab before they read (#117) | not posted – [issue](issue-10-net-read-one-page.md) and [pull request](pr-10-net-read-one-page.md) drafted on 2026-11-02, waiting for the owner's word. Found live the same day on pytree (E-18 before): `listNetsApi` takes parts and flags from `getAll(undefined, true)`, the wires from `SCH_PrimitiveWire.getAll()` (`dispatcher.ts:896`, `:795`); unchanged in 1.8.1 and on `upstream/main` `5f845f0` (2026-11-03), no issue there. The same root as M-6's `all_pages` | `fix/net-read-one-page` | 1.8.1 |

Fork branches in the clone `../easyeda-mcp-pro`, on 1.6.0, pushed to the fork and posted on 2026-11-01 on the owner's
word – M-10's the same evening, on `cde4a39`:

| Branch | Commit | Tests on 1.6.0 |
|---|---|---|
| `fix/stale-sweep-per-request-timeout` | `fix(bridge): stale sweep honours each request's own timeout` | its test file 69 green, extension 568 green, `pnpm verify:fast` green |
| `fix/schematic-pdf-export` | `fix(export): schematic PDF through SCH_ManufactureData.getExportDocumentFile` | extension 569 green, `pnpm verify:fast` green; the whole server suite as on `upstream/main`: green but for the test that expects no ngspice (installed here) |
| `feat/api-call-max-depth` | `feat(api): optional maxDepth for easyeda_api_call results` | its test files 59 green, extension 571 green, `pnpm verify:fast` green |
| `feat/odb-export` | `feat(export): easyeda_export_odb through getOpenDatabaseDoublePlusFile` | built on 1.6.0: export tests 19 green, extension 573 green, `pnpm verify:fast` green, the whole suite as on `upstream/main` |
| `fix/api-call-null-create` | `fix(api): report an empty create result of easyeda_api_call as a failure` | registry tests 59 green (the new one red without the fix), `pnpm verify:fast` green, the whole suite as on `upstream/main` |
| `fix/pick-place-file-type` | `fix(export): pass the file type to getPickAndPlaceFile` | extension 568 green (two tests red without the fix), `pnpm verify:fast` green, the whole suite as on `upstream/main` |
| `fix/place-component-flags` | `fix(schematic): apply mirror, addIntoBom and addIntoPcb after placement` | extension 571 green (two of the three new tests red without the fix), `pnpm verify:fast` green |
| `fix/rebuild-copper-batch-reconcile` | `fix(pcb): reconcile a net's second fresh pour against copper rebuilt earlier in the batch` | on `upstream/main` `cde4a39`: extension 585 green (one of the two new tests red without the fix), `pnpm verify:fast` green |
| `fix/net-read-one-page` | `fix(schematic): read nets from the focused page only` | rebased onto `upstream/main` `5f845f0` (`1b90910`): extension 619 green (the new test red without the fix), `pnpm verify:fast` green; local, not pushed |

## The component library (EasyEDA / LCSC)

Errors in the library data `edakit part import` reads go to EasyEDA's component library, not to easyeda-mcp-pro.

| # | Topic | Local workaround | Report |
|---|---|---|---|
| 6 | Six symbols differ from their datasheets – a pin number given twice (WS2812B-V5/W, Pico 2, DRV8825), names swapped (XC6206, Pico 2's debug pins), a pad without a pin (DRV8825's PowerPAD, AQY212GS), the LED's pins of a 6N138 named "2" and "NC" | STRUCT.entry compares the cached symbol with the entry and the footprint; the library entries say where they follow the datasheet (`symbol_differs`, handbook 4.4) | [report draft](issue-6-easyeda-symbols.md) – not sent |
